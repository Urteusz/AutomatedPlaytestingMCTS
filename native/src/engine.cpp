#include "engine.hpp"

#include <deque>
#include <queue>

namespace md2 {

// --- budowa poziomu ---------------------------------------------------------

bool Level::sight_is_clear(int start, int end) const {
    // Port `MiniDungeon._sight_is_clear` - DDA na liczbach calkowitych.
    int start_row = row_of(start), start_col = col_of(start);
    int end_row = row_of(end), end_col = col_of(end);
    int delta_row = end_row - start_row;
    int delta_column = end_col - start_col;
    int step_row = (delta_row > 0) - (delta_row < 0);
    int step_column = (delta_column > 0) - (delta_column < 0);
    int span_row = delta_row < 0 ? -delta_row : delta_row;
    int span_column = delta_column < 0 ? -delta_column : delta_column;
    int row = start_row, column = start_col;
    int crossings_row = 1, crossings_column = 1;
    while (crossings_row <= span_row || crossings_column <= span_column) {
        if (crossings_row > span_row) {
            column += step_column;
            ++crossings_column;
        } else if (crossings_column > span_column) {
            row += step_row;
            ++crossings_row;
        } else {
            int row_boundary = (2 * crossings_row - 1) * span_column;
            int column_boundary = (2 * crossings_column - 1) * span_row;
            if (row_boundary < column_boundary) {
                row += step_row;
                ++crossings_row;
            } else if (column_boundary < row_boundary) {
                column += step_column;
                ++crossings_column;
            } else {
                // promien trafil w styk czterech kafli
                bool open = passable(row + step_row, column) || passable(row, column + step_column);
                if (!open) return false;
                row += step_row;
                column += step_column;
                ++crossings_row;
                ++crossings_column;
            }
        }
        if ((row != end_row || column != end_col) && !passable(row, column)) return false;
    }
    return true;
}

bool Level::line_of_sight(int start, int end) const {
    if (start == end) return false;
    if (!passable(row_of(end), col_of(end))) return false;
    int delta_row = row_of(end) - row_of(start);
    int delta_column = col_of(end) - col_of(start);
    if (delta_row && delta_column) {
        if (rules.los_geometry == 0) return false;  // axis4
        if (rules.los_geometry == 1) {              // axis8
            int ar = delta_row < 0 ? -delta_row : delta_row;
            int ac = delta_column < 0 ? -delta_column : delta_column;
            if (ar != ac) return false;
        }
    }
    return sight_is_clear(start, end);
}

void Level::compute_neighbors() {
    neighbors.assign(static_cast<std::size_t>(ncells) * 4, -1);
    for (int cell = 0; cell < ncells; ++cell) {
        int row = row_of(cell), col = col_of(cell);
        for (int dir = 0; dir < 4; ++dir) {
            int nr = row + DIR_DR[dir], nc = col + DIR_DC[dir];
            if (passable(nr, nc)) neighbors[static_cast<std::size_t>(cell) * 4 + dir] = nr * width + nc;
        }
    }
}

void Level::compute_exit_distances() {
    // BFS 0-1 od wyjscia; portal to krawedz o koszcie 0 (appendleft w Pythonie)
    exit_distance.assign(ncells, -1);
    std::deque<int> queue;
    exit_distance[exit_cell] = 0;
    queue.push_back(exit_cell);
    while (!queue.empty()) {
        int position = queue.front();
        queue.pop_front();
        int linked = rules.pe_portals ? portal_link[position] : -1;
        if (linked >= 0 && exit_distance[linked] < 0) {
            exit_distance[linked] = exit_distance[position];
            queue.push_front(linked);
        }
        for (int dir = 0; dir < 4; ++dir) {
            int neighbour = neighbors[static_cast<std::size_t>(position) * 4 + dir];
            if (neighbour < 0 || exit_distance[neighbour] >= 0) continue;
            exit_distance[neighbour] = exit_distance[position] + 1;
            queue.push_back(neighbour);
        }
    }
    exit_distance_span = 0;
    for (int cell = 0; cell < ncells; ++cell) {
        if (exit_distance[cell] > exit_distance_span) exit_distance_span = exit_distance[cell];
    }
}

void Level::compute_los() {
    std::size_t bits = static_cast<std::size_t>(ncells) * ncells;
    los.assign((bits + 63) / 64, 0ull);
    for (int from = 0; from < ncells; ++from) {
        if (wall[from]) continue;  // ze sciany nikt nie patrzy
        for (int to = 0; to < ncells; ++to) {
            if (!line_of_sight(from, to)) continue;
            std::size_t index = static_cast<std::size_t>(from) * ncells + to;
            los[index >> 6] |= 1ull << (index & 63);
        }
    }
}

std::shared_ptr<Level> Level::build(const std::vector<std::string>& rows,
                                    const std::vector<std::pair<int, int>>& portal_pairs,
                                    const Rules& rules) {
    auto level = std::make_shared<Level>();
    level->rules = rules;
    if (rows.empty()) throw std::runtime_error("Map is empty");
    level->height = static_cast<int>(rows.size());
    level->width = static_cast<int>(rows[0].size());
    for (const auto& row : rows) {
        if (static_cast<int>(row.size()) != level->width) throw std::runtime_error("Map is not rectangular");
    }
    level->ncells = level->width * level->height;
    if (level->ncells > MAX_CELLS) throw std::runtime_error("Map exceeds MAX_CELLS");
    level->wall.assign(level->ncells, 0);
    level->obj_template.assign(level->ncells, OBJ_NONE);
    level->portal_link.assign(level->ncells, -1);

    int entrances = 0, exits = 0;
    for (int row = 0; row < level->height; ++row) {
        for (int col = 0; col < level->width; ++col) {
            char symbol = rows[row][col];
            int cell = row * level->width + col;
            switch (symbol) {
                case '#': level->wall[cell] = 1; break;
                case '.': break;
                case 'E': level->entrance = cell; ++entrances; break;
                case 'X': level->obj_template[cell] = OBJ_EXIT; level->exit_cell = cell; ++exits; break;
                case 'r': level->obj_template[cell] = OBJ_TREASURE; break;
                case 'p': level->obj_template[cell] = OBJ_POTION; break;
                case 'P': level->obj_template[cell] = OBJ_PORTAL; break;
                case '^': level->obj_template[cell] = OBJ_TRAP; break;
                case 'g': level->npc_specs.push_back({NPC_GOBLIN, cell}); break;
                case 'w': level->npc_specs.push_back({NPC_WIZARD, cell}); break;
                case 'b': level->npc_specs.push_back({NPC_BLOB, cell}); break;
                case 'o': level->npc_specs.push_back({NPC_OGRE, cell}); break;
                case 'M': level->npc_specs.push_back({NPC_MINITAUR, cell}); break;
                default: throw std::runtime_error(std::string("Map contains unknown symbol: ") + symbol);
            }
            if (level->obj_template[cell] != OBJ_NONE) level->object_cells.push_back(cell);
        }
    }
    if (entrances != 1 || exits != 1) throw std::runtime_error("Map needs exactly one E and one X");
    if (static_cast<int>(level->npc_specs.size()) > MAX_NPCS) throw std::runtime_error("Too many NPCs");

    for (const auto& pair : portal_pairs) {
        level->portal_link[pair.first] = pair.second;
        level->portal_link[pair.second] = pair.first;
    }

    for (int cell = 0; cell < level->ncells; ++cell) {
        if (level->obj_template[cell] == OBJ_POTION) ++level->initial_potions;
        if (level->obj_template[cell] == OBJ_TREASURE) ++level->initial_treasures;
    }
    for (const auto& spec : level->npc_specs) {
        if (spec.kind != NPC_MINITAUR) ++level->initial_killable;
    }
    level->initial_completion =
        level->initial_potions + level->initial_treasures + level->initial_killable;

    level->compute_neighbors();
    level->compute_exit_distances();

    int exit_row = level->row_of(level->exit_cell), exit_col = level->col_of(level->exit_cell);
    for (int cell = 0; cell < level->ncells; ++cell) {
        if (level->wall[cell]) continue;
        int dr = level->row_of(cell) - exit_row;
        int dc = level->col_of(cell) - exit_col;
        int distance = (dr < 0 ? -dr : dr) + (dc < 0 ? -dc : dc);
        if (distance > level->manhattan_span) level->manhattan_span = distance;
    }

    level->compute_los();
    return level;
}

// --- stan -------------------------------------------------------------------

void State::reset(const Level& lvl) {
    level = &lvl;
    std::memcpy(obj, lvl.obj_template.data(), static_cast<std::size_t>(lvl.ncells));
    npc_count = static_cast<std::uint8_t>(lvl.npc_specs.size());
    for (int i = 0; i < npc_count; ++i) {
        const NpcSpec& spec = lvl.npc_specs[i];
        Npc& npc = npcs[i];
        npc.kind = spec.kind;
        npc.alive = 1;
        npc.stunned = 0;
        npc.fancy = 0;
        npc.cell = static_cast<std::int16_t>(spec.cell);
        if (spec.kind == NPC_BLOB) {
            npc.power = static_cast<std::int16_t>(lvl.rules.blob_initial_power);
            npc.hp = npc.power;
        } else {
            npc.power = 1;
            switch (spec.kind) {
                case NPC_GOBLIN: npc.hp = static_cast<std::int16_t>(lvl.rules.goblin_hp); break;
                case NPC_WIZARD: npc.hp = static_cast<std::int16_t>(lvl.rules.wizard_hp); break;
                case NPC_OGRE: npc.hp = static_cast<std::int16_t>(lvl.rules.ogre_hp); break;
                default: npc.hp = 0; break;  // minitaur nie ma HP (nie ginie)
            }
        }
    }
    hero = static_cast<std::int16_t>(lvl.entrance);
    hero_hp = static_cast<std::int16_t>(lvl.rules.hero_start_hp);
    javelin_held = lvl.rules.starts_with_javelin;
    javelin_cell = -1;
    metrics = Metrics();
    done = false;
}

int State::npc_at(int cell, int exclude_id) const {
    // najnizszy initial_order == najnizszy npc_id == najnizszy indeks
    for (int i = 0; i < npc_count; ++i) {
        if (npcs[i].alive && npcs[i].cell == cell && i != exclude_id) return i;
    }
    return -1;
}

int State::legal_actions(ActionCode* out) const {
    if (done) return 0;
    int count = 0;
    for (int dir : level->rules.movement_dirs) {
        if (level->neighbors[static_cast<std::size_t>(hero) * 4 + dir] >= 0) {
            out[count++] = static_cast<ActionCode>(dir);
        }
    }
    if (javelin_held) {
        for (int i = 0; i < npc_count; ++i) {
            if (!npcs[i].alive) continue;
            if (level->has_los(hero, npcs[i].cell)) {
                out[count++] = static_cast<ActionCode>(ACTION_THROW_BASE + i);
            }
        }
    }
    return count;
}

void State::step(ActionCode action) {
    if (done) return;
    metrics.turns += 1;
    if (action < ACTION_THROW_BASE) {
        metrics.steps += 1;
        move_hero(action);
    } else {
        throw_javelin(action - ACTION_THROW_BASE);
    }
    if (!done) run_npc_turn();
}

void State::move_hero(int direction) {
    int target = level->neighbors[static_cast<std::size_t>(hero) * 4 + direction];
    int origin = hero;
    int occupant = npc_at(target);
    if (occupant < 0) {
        hero = static_cast<std::int16_t>(target);
    } else if (npcs[occupant].kind == NPC_MINITAUR && npcs[occupant].stunned > 0) {
        hero = static_cast<std::int16_t>(target);
    } else {
        resolve_hero_npc_collision(occupant);
        bool may_enter = !npcs[occupant].alive ||
                         (npcs[occupant].kind == NPC_MINITAUR && npcs[occupant].stunned > 0);
        if (!done && may_enter) hero = static_cast<std::int16_t>(target);
    }
    if (hero != origin && !done) {
        pickup_javelin();
        apply_hero_object();
    }
}

void State::throw_javelin(int target_id) {
    javelin_held = false;
    javelin_cell = npcs[target_id].cell;
    metrics.javelins += 1;
    damage_npc(target_id, level->rules.javelin_damage, true);
}

int State::npc_collision_damage(const Npc& npc) const {
    if (npc.kind == NPC_BLOB) return npc.power;
    switch (npc.kind) {
        case NPC_GOBLIN: return level->rules.goblin_collision;
        case NPC_WIZARD: return level->rules.wizard_collision;
        case NPC_OGRE: return level->rules.ogre_collision;
        default: return level->rules.minitaur_collision;
    }
}

void State::resolve_hero_npc_collision(int npc_id) {
    int hero_damage = npc_collision_damage(npcs[npc_id]);
    damage_npc(npc_id, level->rules.hero_collision_damage, true);
    damage_hero(hero_damage);
}

void State::resolve_npc_hero_collision(int npc_id) {
    int hero_damage = npc_collision_damage(npcs[npc_id]);
    damage_npc(npc_id, level->rules.hero_collision_damage, true);
    damage_hero(hero_damage);
}

void State::damage_hero(int amount) {
    if (amount <= 0 || done) return;
    hero_hp = static_cast<std::int16_t>(hero_hp - amount);
    if (hero_hp <= 0) {
        hero_hp = 0;
        metrics.died = true;
        done = true;
    }
}

void State::damage_npc(int npc_id, int amount, bool hero_credit) {
    Npc& npc = npcs[npc_id];
    if (!npc.alive || amount <= 0) return;
    if (npc.kind == NPC_MINITAUR) {
        bool was_active = npc.stunned == 0;
        npc.stunned = static_cast<std::uint8_t>(level->rules.minitaur_stun_actions);
        if (was_active) metrics.minitaur_knockouts += 1;
        return;
    }
    if (npc.kind == NPC_BLOB) {
        if (npc.power <= 1) {
            npc.hp = 0;
        } else {
            npc.power -= 1;
            npc.hp = npc.power;
        }
    } else {
        npc.hp = static_cast<std::int16_t>(npc.hp - amount);
    }
    if (npc.hp <= 0) {
        npc.alive = 0;
        if (hero_credit) metrics.monsters += 1;
    }
}

void State::apply_hero_object() {
    std::uint8_t kind = obj[hero];
    if (kind == OBJ_POTION) {
        int healed = hero_hp + level->rules.potion_heal;
        hero_hp = static_cast<std::int16_t>(healed < level->rules.hero_max_hp ? healed
                                                                             : level->rules.hero_max_hp);
        obj[hero] = OBJ_NONE;
        metrics.potions += 1;
    } else if (kind == OBJ_TREASURE) {
        obj[hero] = OBJ_NONE;
        metrics.treasures += 1;
    } else if (kind == OBJ_TRAP) {
        metrics.traps += 1;
        damage_hero(level->rules.trap_damage);
    } else if (kind == OBJ_PORTAL) {
        teleport_hero();
    } else if (kind == OBJ_EXIT) {
        metrics.reached_exit = true;
        done = true;
    }
}

void State::pickup_javelin() {
    if (!javelin_held && javelin_cell == hero) {
        javelin_held = true;
        javelin_cell = -1;
    }
}

void State::teleport_hero() {
    int destination = level->portal_link[hero];
    if (destination < 0) return;
    if (npc_at(destination) >= 0) return;  // portal_blocked
    hero = static_cast<std::int16_t>(destination);
    metrics.teleports += 1;
    pickup_javelin();
}

void State::teleport_npc(int npc_id) {
    Npc& npc = npcs[npc_id];
    int destination = level->portal_link[npc.cell];
    if (destination < 0) return;
    if (destination == hero || npc_at(destination) >= 0) return;  // portal_blocked
    npc.cell = static_cast<std::int16_t>(destination);
}

void State::run_npc_turn() {
    for (int npc_id = 0; npc_id < npc_count; ++npc_id) {
        if (done) break;
        Npc& npc = npcs[npc_id];
        if (!npc.alive) continue;
        if (npc.stunned > 0) {
            npc.stunned -= 1;
            continue;
        }
        act_npc(npc_id);
    }
}

void State::act_npc(int npc_id) {
    switch (npcs[npc_id].kind) {
        case NPC_GOBLIN: act_goblin(npc_id); break;
        case NPC_WIZARD: act_wizard(npc_id); break;
        case NPC_BLOB: act_target_seeker(npc_id, OBJ_POTION); break;
        case NPC_OGRE: act_target_seeker(npc_id, OBJ_TREASURE); break;
        default: act_minitaur(npc_id); break;
    }
}

void State::act_goblin(int npc_id) {
    int from = npcs[npc_id].cell;
    if (!level->has_los(from, hero)) return;  // npc_stay: no_los
    move_npc_or_stay(npc_id, next_step_bfs(from, hero, npc_id));
}

void State::act_wizard(int npc_id) {
    int from = npcs[npc_id].cell;
    if (level->has_los(from, hero)) {
        int distance = level->sight_distance(from, hero);
        if (distance <= level->rules.wizard_ranged_range) {
            damage_hero(level->rules.wizard_ranged_damage);
            return;
        }
    } else if (!level->rules.wizard_moves_without_los) {
        return;  // npc_stay: no_los
    }
    move_npc_or_stay(npc_id, next_step_bfs(from, hero, npc_id));
}

void State::act_target_seeker(int npc_id, std::uint8_t preferred) {
    int from = npcs[npc_id].cell;
    bool found = false;
    int best_distance = 0, best_flag = 0, best_row = 0, best_col = 0, best_cell = -1;
    auto consider = [&](int distance, int flag, int cell) {
        int row = level->row_of(cell), col = level->col_of(cell);
        if (!found || distance < best_distance ||
            (distance == best_distance &&
             (flag < best_flag ||
              (flag == best_flag &&
               (row < best_row || (row == best_row && col < best_col)))))) {
            found = true;
            best_distance = distance;
            best_flag = flag;
            best_row = row;
            best_col = col;
            best_cell = cell;
        }
    };
    if (level->has_los(from, hero)) consider(level->sight_distance(from, hero), 1, hero);
    for (int cell : level->object_cells) {
        if (obj[cell] != preferred) continue;
        if (!level->has_los(from, cell)) continue;
        consider(level->sight_distance(from, cell), 0, cell);
    }
    if (!found) return;  // npc_stay: no_target
    move_npc_or_stay(npc_id, next_step_bfs(from, best_cell, npc_id));
}

void State::act_minitaur(int npc_id) {
    int from = npcs[npc_id].cell;
    if (from == hero) {
        resolve_npc_hero_collision(npc_id);
        return;
    }
    move_npc_or_stay(npc_id, next_step_astar(from, hero));
}

void State::move_npc_or_stay(int npc_id, int next_cell) {
    if (next_cell < 0 || next_cell == npcs[npc_id].cell) return;
    move_npc(npc_id, next_cell);
}

void State::move_npc(int npc_id, int destination) {
    Npc& npc = npcs[npc_id];
    if (!npc.alive) return;
    if (destination == hero) {
        resolve_npc_hero_collision(npc_id);
        return;
    }
    int occupant = npc_at(destination, npc_id);
    if (occupant >= 0) {
        if (npc.kind == NPC_BLOB && npcs[occupant].kind == NPC_BLOB) {
            merge_blobs(npc_id, occupant);
        } else {
            resolve_npc_npc_collision(npc_id, occupant);
        }
        return;
    }
    npc.cell = static_cast<std::int16_t>(destination);
    apply_npc_object(npc_id);
}

void State::resolve_npc_npc_collision(int mover_id, int occupant_id) {
    int destination = npcs[occupant_id].cell;
    int mover_damage = npc_collision_damage(npcs[mover_id]);
    int occupant_damage = npc_collision_damage(npcs[occupant_id]);
    damage_npc(occupant_id, mover_damage, false);
    damage_npc(mover_id, occupant_damage, false);
    if (npcs[mover_id].alive && !npcs[occupant_id].alive) {
        npcs[mover_id].cell = static_cast<std::int16_t>(destination);
        apply_npc_object(mover_id);
    }
}

void State::merge_blobs(int mover_id, int occupant_id) {
    int destination = npcs[occupant_id].cell;
    // zostaje blob, ktory byl wczesniej na mapie (initial_order == npc_id)
    int survivor = mover_id <= occupant_id ? mover_id : occupant_id;
    int removed = survivor == mover_id ? occupant_id : mover_id;
    int power = npcs[mover_id].power + npcs[occupant_id].power;
    if (power > level->rules.blob_max_power) power = level->rules.blob_max_power;
    npcs[survivor].power = static_cast<std::int16_t>(power);
    npcs[survivor].hp = static_cast<std::int16_t>(power);
    npcs[survivor].cell = static_cast<std::int16_t>(destination);
    npcs[removed].alive = 0;
}

void State::apply_npc_object(int npc_id) {
    Npc& npc = npcs[npc_id];
    if (!npc.alive) return;
    std::uint8_t kind = obj[npc.cell];
    if (kind == OBJ_POTION && npc.kind == NPC_BLOB) {
        obj[npc.cell] = OBJ_NONE;
    } else if (kind == OBJ_TREASURE && npc.kind == NPC_OGRE) {
        obj[npc.cell] = OBJ_NONE;
        npc.fancy = 1;
    } else if (kind == OBJ_TRAP) {
        damage_npc(npc_id, level->rules.trap_damage, false);
    } else if (kind == OBJ_PORTAL) {
        teleport_npc(npc_id);
    }
}

// --- szukanie drogi ---------------------------------------------------------

int State::next_step_bfs(int start, int goal, int actor_id) const {
    const int ncells = level->ncells;
    bool blocked[MAX_CELLS] = {false};
    std::uint8_t actor_kind = npcs[actor_id].kind;
    if (actor_kind == NPC_GOBLIN || actor_kind == NPC_WIZARD) {
        for (int i = 0; i < npc_count; ++i) {
            if (i == actor_id || !npcs[i].alive) continue;
            if (npcs[i].kind != NPC_GOBLIN && npcs[i].kind != NPC_WIZARD) continue;
            if (npcs[i].cell == goal) continue;
            blocked[npcs[i].cell] = true;
        }
    }
    if (hero != goal) blocked[hero] = true;

    int parents[MAX_CELLS];
    for (int i = 0; i < ncells; ++i) parents[i] = -2;
    int queue[MAX_CELLS];
    int head = 0, tail = 0;
    parents[start] = -1;
    queue[tail++] = start;
    while (head < tail) {
        int current = queue[head++];
        if (current == goal) break;
        for (int dir : level->rules.neighbor_order) {
            int neighbor = level->neighbors[static_cast<std::size_t>(current) * 4 + dir];
            if (neighbor < 0) continue;
            if (parents[neighbor] != -2 || blocked[neighbor]) continue;
            parents[neighbor] = current;
            queue[tail++] = neighbor;
        }
    }
    if (parents[goal] == -2) return -1;
    int current = goal;
    while (parents[current] != -1 && parents[current] != start) current = parents[current];
    return current;
}

namespace {
struct HeapEntry {
    int priority;
    int sequence;
    int cell;
    bool operator>(const HeapEntry& other) const {
        if (priority != other.priority) return priority > other.priority;
        return sequence > other.sequence;
    }
};
}  // namespace

int State::next_step_astar(int start, int goal) const {
    const int ncells = level->ncells;
    auto manhattan = [&](int a, int b) {
        int dr = level->row_of(a) - level->row_of(b);
        int dc = level->col_of(a) - level->col_of(b);
        return (dr < 0 ? -dr : dr) + (dc < 0 ? -dc : dc);
    };
    int parents[MAX_CELLS];
    int costs[MAX_CELLS];
    for (int i = 0; i < ncells; ++i) {
        parents[i] = -2;
        costs[i] = -1;
    }
    std::priority_queue<HeapEntry, std::vector<HeapEntry>, std::greater<HeapEntry>> frontier;
    int sequence = 0;
    frontier.push({manhattan(start, goal), sequence, start});
    parents[start] = -1;
    costs[start] = 0;
    while (!frontier.empty()) {
        HeapEntry entry = frontier.top();
        frontier.pop();
        int current = entry.cell;
        if (current == goal) break;
        for (int dir : level->rules.neighbor_order) {
            int neighbor = level->neighbors[static_cast<std::size_t>(current) * 4 + dir];
            if (neighbor < 0) continue;
            int new_cost = costs[current] + 1;
            if (costs[neighbor] >= 0 && new_cost >= costs[neighbor]) continue;
            costs[neighbor] = new_cost;
            parents[neighbor] = current;
            ++sequence;
            frontier.push({new_cost + manhattan(neighbor, goal), sequence, neighbor});
        }
    }
    if (parents[goal] == -2) return -1;
    int current = goal;
    while (parents[current] != -1 && parents[current] != start) current = parents[current];
    return current;
}

}  // namespace md2
