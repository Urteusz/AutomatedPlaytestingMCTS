// Granica Python <-> C++. Jedno przejscie na PARTIE, nie na iteracje: przy
// ~800 przejsciach na iteracje narzut granicy (29 ns) zjada caly zysk - to
// zmierzone, patrz README. Dlatego `evaluate` dostaje wszystko, czego
// potrzebuje, i oddaje gotowe metryki.
//
// Regul ani person nie czytamy tu z JSON-a: podaje je cienki wrapper
// `mdnative.py`, ktory czyta te same pliki co Python. Dzieki temu port nie ma
// wlasnej kopii regul, ktora moglaby sie rozjechac z `data/rules/`.
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <array>
#include <string>
#include <vector>

#include "engine.hpp"
#include "mcts.hpp"

namespace py = pybind11;
using namespace md2;

namespace {

Rules rules_from_dict(const py::dict& source) {
    Rules rules;
    auto integer = [&](const char* key, int fallback) {
        return source.contains(key) ? source[key].cast<int>() : fallback;
    };
    auto boolean = [&](const char* key, bool fallback) {
        return source.contains(key) ? source[key].cast<bool>() : fallback;
    };
    rules.hero_start_hp = integer("hero_start_hp", 10);
    rules.hero_max_hp = integer("hero_max_hp", 10);
    rules.hero_collision_damage = integer("hero_collision_damage", 1);
    rules.starts_with_javelin = boolean("starts_with_javelin", true);
    rules.javelin_damage = integer("javelin_damage", 1);
    rules.potion_heal = integer("potion_heal", 1);
    rules.trap_damage = integer("trap_damage", 1);
    rules.goblin_hp = integer("goblin_hp", 1);
    rules.goblin_collision = integer("goblin_collision", 1);
    rules.wizard_hp = integer("wizard_hp", 1);
    rules.wizard_collision = integer("wizard_collision", 0);
    rules.wizard_ranged_damage = integer("wizard_ranged_damage", 1);
    rules.wizard_ranged_range = integer("wizard_ranged_range", 5);
    rules.wizard_moves_without_los = boolean("wizard_moves_without_los", false);
    rules.blob_initial_power = integer("blob_initial_power", 1);
    rules.blob_max_power = integer("blob_max_power", 3);
    rules.ogre_hp = integer("ogre_hp", 2);
    rules.ogre_collision = integer("ogre_collision", 2);
    rules.minitaur_collision = integer("minitaur_collision", 1);
    rules.minitaur_stun_actions = integer("minitaur_stun_actions", 3);
    rules.los_geometry = integer("los_geometry", 1);
    rules.los_distance_metric = integer("los_distance_metric", 0);
    rules.pe_portals = boolean("pe_portals", true);
    if (source.contains("movement_dirs")) {
        rules.movement_dirs = source["movement_dirs"].cast<std::vector<int>>();
    }
    if (source.contains("neighbor_order")) {
        rules.neighbor_order = source["neighbor_order"].cast<std::vector<int>>();
    }
    return rules;
}

std::shared_ptr<Level> make_level(const std::vector<std::string>& rows,
                                  const std::vector<std::array<int, 4>>& portal_pairs_rc,
                                  const py::dict& rules_dict) {
    if (rows.empty()) throw std::runtime_error("Map is empty");
    int width = static_cast<int>(rows[0].size());
    std::vector<std::pair<int, int>> pairs;
    pairs.reserve(portal_pairs_rc.size());
    for (const auto& pair : portal_pairs_rc) {
        pairs.emplace_back(pair[0] * width + pair[1], pair[2] * width + pair[3]);
    }
    return Level::build(rows, pairs, rules_from_dict(rules_dict));
}

py::dict evaluate(const std::shared_ptr<Level>& level, const std::string& formula,
                  const std::vector<std::pair<int, double>>& weights, double death_penalty,
                  int core_metric, int seed, long long max_iterations, double time_limit_s,
                  int pe_mode, int utility_pe, int ic_mode, int fallback, int policy_kind) {
    Program program = Parser::compile(formula);
    PersonaSpec persona;
    persona.weights = weights;
    persona.death_penalty = death_penalty;
    persona.core_metric = core_metric;
    Conventions conventions;
    conventions.pe_mode = pe_mode;
    conventions.utility_pe = utility_pe;
    conventions.ic_mode = ic_mode;

    Outcome outcome;
    const State* final_state = nullptr;
    Tree tree(*level, program, policy_kind, persona, conventions);
    tree.set_seed(seed);
    {
        py::gil_scoped_release release;  // pula procesow tego nie potrzebuje, watki tak
        outcome = tree.play_single_tree(max_iterations, time_limit_s, fallback);
    }
    final_state = &tree.env();

    py::dict result;
    result["utility"] = utility(*final_state, persona, conventions);
    result["core"] = metric_value(*final_state, core_metric, conventions);
    result["win"] = outcome.metrics.reached_exit ? 1 : 0;
    result["died"] = outcome.metrics.died ? 1 : 0;
    result["iterations"] = outcome.iterations;
    result["from_tree"] = outcome.from_tree;
    result["nodes"] = static_cast<long long>(tree.node_count());
    result["steps"] = outcome.metrics.steps;
    result["turns"] = outcome.metrics.turns;
    result["health_left"] = static_cast<int>(outcome.hero_hp);
    result["potions"] = outcome.metrics.potions;
    result["treasures"] = outcome.metrics.treasures;
    result["monsters"] = outcome.metrics.monsters;
    result["javelins"] = outcome.metrics.javelins;
    result["teleports"] = outcome.metrics.teleports;
    result["traps"] = outcome.metrics.traps;
    result["minitaur_knockouts"] = outcome.metrics.minitaur_knockouts;
    result["monster_ratio"] = final_state->monster_ratio();
    result["potion_ratio"] = final_state->potion_ratio();
    result["treasure_ratio"] = final_state->treasure_ratio();
    result["interactive_ratio"] = patched_interactive(*final_state, ic_mode);
    result["proximity_to_exit"] = patched_proximity(*final_state, utility_pe);
    result["sequence"] = outcome.sequence;
    return result;
}

// Do testu roznicowego: odegraj zadana sekwencje akcji i oddaj odcisk stanu.
py::dict replay(const std::shared_ptr<Level>& level, const std::vector<int>& actions,
                int ic_mode, int utility_pe) {
    State state;
    state.reset(*level);
    std::vector<int> fingerprints;
    ActionCode legal[MAX_ACTIONS];
    for (int action : actions) {
        if (state.done) break;
        state.step(static_cast<ActionCode>(action));
        fingerprints.push_back(state.hero * 1000 + state.hero_hp);
    }
    py::dict result;
    result["hero"] = static_cast<int>(state.hero);
    result["hero_hp"] = static_cast<int>(state.hero_hp);
    result["done"] = state.done;
    result["steps"] = state.metrics.steps;
    result["turns"] = state.metrics.turns;
    result["monsters"] = state.metrics.monsters;
    result["potions"] = state.metrics.potions;
    result["treasures"] = state.metrics.treasures;
    result["javelins"] = state.metrics.javelins;
    result["teleports"] = state.metrics.teleports;
    result["traps"] = state.metrics.traps;
    result["minitaur_knockouts"] = state.metrics.minitaur_knockouts;
    result["reached_exit"] = state.metrics.reached_exit;
    result["died"] = state.metrics.died;
    result["legal_count"] = state.legal_actions(legal);
    result["fingerprints"] = fingerprints;
    result["interactive_ratio"] = patched_interactive(state, ic_mode);
    result["proximity_to_exit"] = patched_proximity(state, utility_pe);
    std::vector<int> npc_state;
    for (int i = 0; i < state.npc_count; ++i) {
        npc_state.push_back(state.npcs[i].alive ? state.npcs[i].cell : -1);
    }
    result["npcs"] = npc_state;
    return result;
}

// Do testu generatora: pierwsze n wynikow `randbelow(bound)` dla danego seeda.
std::vector<int> random_probe(int seed, int bound, int count) {
    PyRandom rng(static_cast<std::uint64_t>(seed));
    std::vector<int> values;
    values.reserve(count);
    for (int i = 0; i < count; ++i) {
        values.push_back(static_cast<int>(rng.randbelow(static_cast<std::uint32_t>(bound))));
    }
    return values;
}

}  // namespace

PYBIND11_MODULE(md2native, module) {
    module.doc() = "MiniDungeons 2 - natywny silnik MCTS dla petli fitnessu GP";
    py::class_<Level, std::shared_ptr<Level>>(module, "Level")
        .def_property_readonly("ncells", [](const Level& level) { return level.ncells; })
        .def_property_readonly("exit_distance_span",
                               [](const Level& level) { return level.exit_distance_span; })
        .def_property_readonly("manhattan_span",
                               [](const Level& level) { return level.manhattan_span; });
    module.def("make_level", &make_level, py::arg("rows"), py::arg("portal_pairs"),
               py::arg("rules"));
    module.def("evaluate", &evaluate, py::arg("level"), py::arg("formula"), py::arg("weights"),
               py::arg("death_penalty"), py::arg("core_metric"), py::arg("seed"),
               py::arg("max_iterations"), py::arg("time_limit_s"), py::arg("pe_mode"),
               py::arg("utility_pe"), py::arg("ic_mode"), py::arg("fallback"),
               py::arg("policy_kind") = 0);
    module.def("replay", &replay, py::arg("level"), py::arg("actions"), py::arg("ic_mode") = 0,
               py::arg("utility_pe") = 0);
    module.def("random_probe", &random_probe, py::arg("seed"), py::arg("bound"), py::arg("count"));
}
