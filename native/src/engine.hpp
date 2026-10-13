// Silnik MiniDungeons 2 - port `src/minidungeons/domain/engine.py`.
//
// Podzial na `Level` (niemutowalne: teren, portale, tablica LOS, dystanse do
// wyjscia) i `State` (mutowalny stan partii) odpowiada temu, co `clone()` w
// Pythonie robi recznie: klony wspoldziela teren i dystanse, kopiuja tylko
// stan. Dzieki temu `State` jest POD-em i klonowanie to memcpy.
//
// Kolejnosc iteracji jest czescia kontraktu, nie szczegolem: `legal_actions`,
// tura NPC i `_npc_at` musza dawac te same sekwencje co slowniki Pythona,
// inaczej rozjedzie sie losowanie. NPC maja `npc_id == initial_order`, wiec
// wszystkie trzy porzadki (wstawienia, po id, po initial_order) to rosnacy
// indeks tablicy.
#pragma once

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

namespace md2 {

constexpr int MAX_CELLS = 256;
constexpr int MAX_NPCS = 24;

enum ObjKind : std::uint8_t {
    OBJ_NONE = 0,
    OBJ_EXIT = 1,
    OBJ_TREASURE = 2,
    OBJ_POTION = 3,
    OBJ_PORTAL = 4,
    OBJ_TRAP = 5,
};

enum NpcKind : std::uint8_t {
    NPC_GOBLIN = 0,
    NPC_WIZARD = 1,
    NPC_BLOB = 2,
    NPC_OGRE = 3,
    NPC_MINITAUR = 4,
};

struct Rules {
    int hero_start_hp = 10;
    int hero_max_hp = 10;
    int hero_collision_damage = 1;
    bool starts_with_javelin = true;
    int javelin_damage = 1;
    int potion_heal = 1;
    int trap_damage = 1;
    int goblin_hp = 1, goblin_collision = 1;
    int wizard_hp = 1, wizard_collision = 0, wizard_ranged_damage = 1, wizard_ranged_range = 5;
    bool wizard_moves_without_los = false;
    int blob_initial_power = 1, blob_max_power = 3;
    int ogre_hp = 2, ogre_collision = 2;
    int minitaur_collision = 1, minitaur_stun_actions = 3;
    // "axis4" | "axis8" | "raycast"
    int los_geometry = 1;
    // 0 = chebyshev, 1 = manhattan
    int los_distance_metric = 0;
    // portal jako krawedz o koszcie 0 w BFS do wyjscia (PE); false = `pe_portals=off`
    bool pe_portals = true;
    // indeksy kierunkow (0=N, 1=E, 2=S, 3=W)
    std::vector<int> movement_dirs{0, 1, 2, 3};
    std::vector<int> neighbor_order{0, 1, 2, 3};
};

// dr, dc dla N, E, S, W - kolejnosc jak DIRECTION_DELTA w Pythonie
constexpr int DIR_DR[4] = {-1, 0, 1, 0};
constexpr int DIR_DC[4] = {0, 1, 0, -1};

struct NpcSpec {
    NpcKind kind;
    int cell;
};

// --- poziom (niemutowalny, wspoldzielony przez wszystkie klony) --------------

class Level {
public:
    int width = 0, height = 0, ncells = 0;
    Rules rules;
    std::vector<std::uint8_t> wall;          // 1 = sciana
    std::vector<std::uint8_t> obj_template;  // ObjKind na kafel
    std::vector<int> object_cells;           // kafle z obiektem, w kolejnosci skanu mapy
    std::vector<NpcSpec> npc_specs;
    int entrance = -1, exit_cell = -1;
    std::vector<int> portal_link;   // kafel -> kafel albo -1
    std::vector<int> exit_distance; // BFS 0-1 od wyjscia, -1 = nieosiagalny
    int exit_distance_span = 0;
    int manhattan_span = 0;
    int initial_potions = 0, initial_treasures = 0;
    int initial_killable = 0, initial_completion = 0;
    std::vector<int> neighbors;       // ncells * 4, -1 gdy nieprzechodni
    std::vector<std::uint64_t> los;   // bitmapa ncells x ncells

    int row_of(int cell) const { return cell / width; }
    int col_of(int cell) const { return cell % width; }

    bool passable(int row, int col) const {
        if (row < 0 || row >= height || col < 0 || col >= width) return false;
        return !wall[row * width + col];
    }

    bool has_los(int from, int to) const {
        std::size_t index = static_cast<std::size_t>(from) * ncells + to;
        return (los[index >> 6] >> (index & 63)) & 1ull;
    }

    int sight_distance(int from, int to) const {
        int dr = row_of(from) - row_of(to);
        int dc = col_of(from) - col_of(to);
        if (dr < 0) dr = -dr;
        if (dc < 0) dc = -dc;
        if (rules.los_distance_metric == 1) return dr + dc;
        return dr > dc ? dr : dc;
    }

    static std::shared_ptr<Level> build(const std::vector<std::string>& rows,
                                        const std::vector<std::pair<int, int>>& portal_pairs_rc,
                                        const Rules& rules);

private:
    void compute_neighbors();
    void compute_exit_distances();
    void compute_los();
    bool sight_is_clear(int start, int end) const;
    bool line_of_sight(int start, int end) const;
};

// --- stan partii ------------------------------------------------------------

struct Npc {
    std::uint8_t kind;
    std::uint8_t alive;
    std::uint8_t stunned;
    std::uint8_t fancy;
    std::int16_t cell;
    std::int16_t hp;
    std::int16_t power;
};

struct Metrics {
    int steps = 0, potions = 0, treasures = 0, minitaur_knockouts = 0;
    int monsters = 0, javelins = 0, teleports = 0, traps = 0, turns = 0;
    bool reached_exit = false, died = false;
};

// Akcja: 0..3 = ruch N/E/S/W, 4 + id = rzut oszczepem w NPC o tym id.
using ActionCode = std::int16_t;
constexpr ActionCode ACTION_THROW_BASE = 4;

struct State {
    const Level* level = nullptr;
    std::int16_t hero = 0;
    std::int16_t hero_hp = 0;
    std::int16_t javelin_cell = -1;
    bool javelin_held = false;
    bool done = false;
    std::uint8_t npc_count = 0;
    Npc npcs[MAX_NPCS];
    std::uint8_t obj[MAX_CELLS];
    Metrics metrics;

    void reset(const Level& lvl);
    int legal_actions(ActionCode* out) const;
    void step(ActionCode action);

    // --- metryki ---
    static double ratio(int numerator, int denominator) {
        return denominator ? static_cast<double>(numerator) / denominator : 0.0;
    }
    double potion_ratio() const { return ratio(metrics.potions, level->initial_potions); }
    double treasure_ratio() const { return ratio(metrics.treasures, level->initial_treasures); }
    double monster_ratio() const { return ratio(metrics.monsters, level->initial_killable); }
    double interactive_ratio_combined() const {
        return ratio(metrics.potions + metrics.treasures + metrics.monsters,
                     level->initial_completion);
    }
    double proximity_binary() const { return hero == level->exit_cell ? 0.0 : -1.0; }
    double proximity_normalized() const {
        int distance = level->exit_distance[hero];
        if (distance < 0) return 0.0;
        if (!level->exit_distance_span) return 1.0;
        return 1.0 - static_cast<double>(distance) / level->exit_distance_span;
    }
    double proximity_manhattan() const {
        if (!level->manhattan_span) return 1.0;
        int dr = level->row_of(hero) - level->row_of(level->exit_cell);
        int dc = level->col_of(hero) - level->col_of(level->exit_cell);
        int distance = (dr < 0 ? -dr : dr) + (dc < 0 ? -dc : dc);
        return 1.0 - static_cast<double>(distance) / level->manhattan_span;
    }
    double proximity_graded() const {
        int distance = level->exit_distance[hero];
        if (distance < 0) return -1.0;
        if (!level->exit_distance_span) return 0.0;
        return -static_cast<double>(distance) / level->exit_distance_span;
    }

private:
    int npc_at(int cell, int exclude_id = -1) const;
    void move_hero(int direction);
    void throw_javelin(int target_id);
    void resolve_hero_npc_collision(int npc_id);
    void resolve_npc_hero_collision(int npc_id);
    void resolve_npc_npc_collision(int mover_id, int occupant_id);
    void merge_blobs(int mover_id, int occupant_id);
    void damage_hero(int amount);
    void damage_npc(int npc_id, int amount, bool hero_credit);
    void apply_hero_object();
    void apply_npc_object(int npc_id);
    void pickup_javelin();
    void teleport_hero();
    void teleport_npc(int npc_id);
    void run_npc_turn();
    void act_npc(int npc_id);
    void act_goblin(int npc_id);
    void act_wizard(int npc_id);
    void act_target_seeker(int npc_id, std::uint8_t preferred);
    void act_minitaur(int npc_id);
    void move_npc_or_stay(int npc_id, int next_cell);
    void move_npc(int npc_id, int destination);
    int npc_collision_damage(const Npc& npc) const;
    int next_step_bfs(int start, int goal, int actor_id) const;
    int next_step_astar(int start, int goal) const;
};

}  // namespace md2
