// MCTS i fitness - port `domain/mcts.py`, `domain/personas.py` i
// `domain/gp_fitness.py`.
//
// Konwencje (`utility_pe`, `ic_mode`) sa tu tym, czym w Pythonie jest
// monkey-patch `metric_values` z `gp_fitness._configure_conventions`: wchodza
// i do nagrody propagowanej w drzewie, i do terminali, i do fitnessu na koncu
// partii. Wagi person przychodza z `personas.json` w oryginalnej kolejnosci,
// bo suma zmiennoprzecinkowa nie jest przemienna.
#pragma once

#include <algorithm>
#include <chrono>
#include <cmath>
#include <limits>
#include <vector>

#include "engine.hpp"
#include "expr.hpp"
#include "pyrandom.hpp"

namespace md2 {

constexpr int MAX_ACTIONS = 4 + MAX_NPCS;

enum MetricId {
    M_PROXIMITY = 0, M_STEPS = 1, M_MONSTER_RATIO = 2, M_TREASURE_RATIO = 3,
    M_POTION_RATIO = 4, M_INTERACTIVE_RATIO = 5, M_HEALTH_LEFT = 6, M_TURNS = 7,
    M_JAVELINS = 8, M_TELEPORTS = 9, M_TRAPS = 10, M_MINITAUR_KNOCKOUTS = 11,
    M_REACHED_EXIT = 12, M_DIED = 13, M_INTERACTIVE_NON_MONSTER = 14,
};

struct Conventions {
    int utility_pe = 0;  // 0 binary, 1 normalized, 2 manhattan
    int ic_mode = 0;     // 0 combined, 1 mean3
    int pe_mode = 0;     // 0 binary, 1 normalized, 2 manhattan, 3 graded
};

struct PersonaSpec {
    std::vector<std::pair<int, double>> weights;  // kolejnosc z personas.json
    double death_penalty = 5.0;
    int core_metric = M_REACHED_EXIT;
};

inline double patched_proximity(const State& state, int utility_pe) {
    if (utility_pe == 1) return state.proximity_normalized();
    if (utility_pe == 2) return state.proximity_manhattan();
    return state.proximity_binary();
}

inline double patched_interactive(const State& state, int ic_mode) {
    if (ic_mode == 1) {
        return (state.monster_ratio() + state.potion_ratio() + state.treasure_ratio()) / 3.0;
    }
    return state.interactive_ratio_combined();
}

inline double resolve_pe(const State& state, int pe_mode) {
    switch (pe_mode) {
        case 1: return state.proximity_normalized();
        case 2: return state.proximity_manhattan();
        case 3: return state.proximity_graded();
        default: return state.proximity_binary();
    }
}

inline double metric_value(const State& state, int metric, const Conventions& conventions) {
    switch (metric) {
        case M_PROXIMITY: return patched_proximity(state, conventions.utility_pe);
        case M_STEPS: return static_cast<double>(state.metrics.steps);
        case M_MONSTER_RATIO: return state.monster_ratio();
        case M_TREASURE_RATIO: return state.treasure_ratio();
        case M_POTION_RATIO: return state.potion_ratio();
        case M_INTERACTIVE_RATIO: return patched_interactive(state, conventions.ic_mode);
        case M_HEALTH_LEFT: return static_cast<double>(state.hero_hp);
        case M_TURNS: return static_cast<double>(state.metrics.turns);
        case M_JAVELINS: return static_cast<double>(state.metrics.javelins);
        case M_TELEPORTS: return static_cast<double>(state.metrics.teleports);
        case M_TRAPS: return static_cast<double>(state.metrics.traps);
        case M_MINITAUR_KNOCKOUTS: return static_cast<double>(state.metrics.minitaur_knockouts);
        case M_REACHED_EXIT: return state.metrics.reached_exit ? 1.0 : 0.0;
        case M_DIED: return state.metrics.died ? 1.0 : 0.0;
        default:
            return State::ratio(state.metrics.potions + state.metrics.treasures,
                                state.level->initial_potions + state.level->initial_treasures);
    }
}

inline double utility(const State& state, const PersonaSpec& persona,
                      const Conventions& conventions) {
    double score = 0.0;
    for (const auto& entry : persona.weights) {
        score += metric_value(state, entry.first, conventions) * entry.second;
    }
    if (state.metrics.died) score -= persona.death_penalty;
    return score;
}

inline void terminal_values(const State& state, const Conventions& conventions, double* out) {
    out[T_ST] = static_cast<double>(state.metrics.steps);
    out[T_PE] = patched_proximity(state, conventions.utility_pe);
    out[T_PD] = state.potion_ratio();
    out[T_TO] = state.treasure_ratio();
    out[T_MTK] = static_cast<double>(state.metrics.minitaur_knockouts);
    out[T_MS] = state.monster_ratio();
    out[T_JT] = static_cast<double>(state.metrics.javelins);
    out[T_HL] = static_cast<double>(state.hero_hp);
    out[T_TU] = static_cast<double>(state.metrics.teleports);
    out[T_TS] = static_cast<double>(state.metrics.traps);
    out[T_IC] = patched_interactive(state, conventions.ic_mode);
    if (conventions.pe_mode != 0) out[T_PE] = resolve_pe(state, conventions.pe_mode);
    out[T_HL] /= static_cast<double>(state.level->rules.hero_max_hp);
}

// --- drzewo -----------------------------------------------------------------

struct Node {
    State env;
    int parent = -1;
    ActionCode action = -1;
    int visits = 0;
    double total_utility = 0.0;
    bool exhausted = false;
    std::uint8_t untried_count = 0;
    std::uint8_t child_count = 0;
    ActionCode untried[MAX_ACTIONS];
    int children[MAX_ACTIONS];
    double terminal_sums[TERMINAL_COUNT];
};

struct Outcome {
    Metrics metrics;
    double hero_hp = 0.0;
    long long iterations = 0;
    bool from_tree = false;
    std::vector<ActionCode> sequence;
};

class Tree {
public:
    Tree(const Level& level, const Program& program, int policy_kind,
         const PersonaSpec& persona, const Conventions& conventions)
        : level_(level), program_(program), policy_kind_(policy_kind),
          persona_(persona), conventions_(conventions) {
        env_.reset(level);
        nodes_.reserve(1024);
        make_node(env_, -1, -1);
    }

    Outcome play_single_tree(long long max_iterations, double time_limit_s, int fallback) {
        PyRandom rng(static_cast<std::uint64_t>(seed_));
        std::vector<ActionCode> winning;
        bool has_winning = false;
        long long iterations = build_tree(rng, max_iterations, time_limit_s, winning, has_winning);

        Outcome outcome;
        outcome.iterations = iterations;
        outcome.from_tree = has_winning;
        outcome.sequence = has_winning ? winning : fallback_sequence(fallback);
        for (ActionCode action : outcome.sequence) {
            if (env_.done) break;
            env_.step(action);
        }
        outcome.metrics = env_.metrics;
        outcome.hero_hp = env_.hero_hp;
        return outcome;
    }

    void set_seed(int seed) { seed_ = seed; }
    const State& env() const { return env_; }
    std::size_t node_count() const { return nodes_.size(); }

private:
    const Level& level_;
    const Program& program_;
    int policy_kind_;
    PersonaSpec persona_;
    Conventions conventions_;
    State env_;
    std::vector<Node> nodes_;
    int seed_ = 0;

    int make_node(const State& state, int parent, ActionCode action) {
        nodes_.emplace_back();
        Node& node = nodes_.back();
        node.env = state;
        node.parent = parent;
        node.action = action;
        node.untried_count = static_cast<std::uint8_t>(node.env.legal_actions(node.untried));
        node.exhausted = node.untried_count == 0;
        for (int i = 0; i < TERMINAL_COUNT; ++i) node.terminal_sums[i] = 0.0;
        return static_cast<int>(nodes_.size()) - 1;
    }

    // pierwszy z maksymalnych wygrywa - jak `max()` w Pythonie
    int select_child(int node_index) {
        const Node& parent = nodes_[node_index];
        int best = -1;
        double best_score = -std::numeric_limits<double>::infinity();
        double terminals[TERMINAL_COUNT];
        for (int i = 0; i < parent.child_count; ++i) {
            int child_index = parent.children[i];
            const Node& child = nodes_[child_index];
            if (child.exhausted) continue;
            double score;
            if (policy_kind_ == 1) {
                double average = child.total_utility / child.visits;
                score = average + std::sqrt(2.0) * std::sqrt(std::log(static_cast<double>(parent.visits)) /
                                                             child.visits);
            } else {
                if (child.visits) {
                    for (int t = 0; t < TERMINAL_COUNT; ++t) {
                        terminals[t] = child.terminal_sums[t] / child.visits;
                    }
                } else {
                    for (int t = 0; t < TERMINAL_COUNT; ++t) terminals[t] = child.terminal_sums[t];
                }
                score = program_.eval(terminals, child.total_utility / child.visits);
            }
            if (score > best_score) {
                best_score = score;
                best = child_index;
            }
        }
        return best;
    }

    bool has_viable_child(int node_index) const {
        const Node& node = nodes_[node_index];
        for (int i = 0; i < node.child_count; ++i) {
            if (!nodes_[node.children[i]].exhausted) return true;
        }
        return false;
    }

    int expand(int node_index, PyRandom& rng) {
        std::uint32_t pick = rng.randbelow(nodes_[node_index].untried_count);
        ActionCode chosen = nodes_[node_index].untried[pick];
        Node& node = nodes_[node_index];
        for (int i = static_cast<int>(pick); i + 1 < node.untried_count; ++i) {
            node.untried[i] = node.untried[i + 1];
        }
        node.untried_count -= 1;
        State child_state = node.env;
        child_state.step(chosen);
        int child_index = make_node(child_state, node_index, chosen);
        // uwaga: `node` moze byc uniewaznione przez realokacje w make_node
        Node& parent = nodes_[node_index];
        parent.children[parent.child_count++] = child_index;
        return child_index;
    }

    void rollout(const State& start, PyRandom& rng, double& value, double* terminals) {
        State sim = start;
        ActionCode legal[MAX_ACTIONS];
        for (int depth = 0; depth < 10; ++depth) {
            int count = sim.legal_actions(legal);
            if (count == 0) break;
            sim.step(legal[rng.randbelow(static_cast<std::uint32_t>(count))]);
        }
        terminal_values(sim, conventions_, terminals);
        value = utility(sim, persona_, conventions_);
    }

    void refresh_exhausted(int node_index) {
        Node& node = nodes_[node_index];
        if (node.exhausted || node.untried_count || node.child_count == 0) return;
        for (int i = 0; i < node.child_count; ++i) {
            if (!nodes_[node.children[i]].exhausted) return;
        }
        node.exhausted = true;
    }

    void backpropagate(int node_index, double value, const double* terminals) {
        int current = node_index;
        while (current >= 0) {
            Node& node = nodes_[current];
            node.visits += 1;
            node.total_utility += value;
            for (int t = 0; t < TERMINAL_COUNT; ++t) node.terminal_sums[t] += terminals[t];
            refresh_exhausted(current);
            current = nodes_[current].parent;
        }
    }

    int iterate(PyRandom& rng) {
        int node_index = 0;
        while (nodes_[node_index].untried_count == 0 && has_viable_child(node_index)) {
            node_index = select_child(node_index);
        }
        if (nodes_[node_index].untried_count > 0 && !nodes_[node_index].env.done) {
            node_index = expand(node_index, rng);
        }
        double value = 0.0;
        double terminals[TERMINAL_COUNT];
        rollout(nodes_[node_index].env, rng, value, terminals);
        backpropagate(node_index, value, terminals);
        return node_index;
    }

    long long build_tree(PyRandom& rng, long long max_iterations, double time_limit_s,
                         std::vector<ActionCode>& winning, bool& has_winning) {
        long long iterations = 0;
        auto start = std::chrono::steady_clock::now();
        while (!nodes_[0].exhausted) {
            if (time_limit_s > 0.0) {
                std::chrono::duration<double> elapsed = std::chrono::steady_clock::now() - start;
                if (elapsed.count() >= time_limit_s) break;
            }
            if (max_iterations > 0 && iterations >= max_iterations) break;
            iterations += 1;
            int node_index = iterate(rng);
            const Node& node = nodes_[node_index];
            if (node.env.done && node.env.metrics.reached_exit) {
                winning = path_to(node_index);
                has_winning = true;
                return iterations;
            }
        }
        has_winning = false;
        return iterations;
    }

    std::vector<ActionCode> path_to(int node_index) const {
        std::vector<ActionCode> actions;
        int current = node_index;
        while (nodes_[current].parent >= 0) {
            actions.push_back(nodes_[current].action);
            current = nodes_[current].parent;
        }
        std::reverse(actions.begin(), actions.end());
        return actions;
    }

    std::vector<ActionCode> fallback_sequence(int fallback) {
        if (fallback == 0) return best_utility_node_sequence();
        std::vector<ActionCode> actions;
        int node_index = 0;
        while (nodes_[node_index].child_count > 0) {
            const Node& node = nodes_[node_index];
            int best = -1;
            double best_score = -std::numeric_limits<double>::infinity();
            for (int i = 0; i < node.child_count; ++i) {
                const Node& child = nodes_[node.children[i]];
                double score = fallback == 1 ? child.total_utility / child.visits
                                             : static_cast<double>(child.visits);
                if (score > best_score) {
                    best_score = score;
                    best = node.children[i];
                }
            }
            node_index = best;
            actions.push_back(nodes_[node_index].action);
        }
        return actions;
    }

    std::vector<ActionCode> best_utility_node_sequence() {
        int best_node = 0;
        double best_score = utility(nodes_[0].env, persona_, conventions_);
        int best_depth = 0;
        std::vector<std::pair<int, int>> stack;
        stack.emplace_back(0, 0);
        while (!stack.empty()) {
            auto entry = stack.back();
            stack.pop_back();
            double score = utility(nodes_[entry.first].env, persona_, conventions_);
            if (score > best_score || (score == best_score && entry.second < best_depth)) {
                best_node = entry.first;
                best_score = score;
                best_depth = entry.second;
            }
            const Node& node = nodes_[entry.first];
            for (int i = 0; i < node.child_count; ++i) {
                stack.emplace_back(node.children[i], entry.second + 1);
            }
        }
        return path_to(best_node);
    }
};

}  // namespace md2
