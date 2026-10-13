// Parser i ewaluator formul tree policy - port `domain/expression.py`.
//
// Python parsuje wyrazenie `ast`-em, wiec priorytety i lacznosc sa pythonowe:
// unarny minus wiaze mocniej niz `*`, a `-x` dla stalej zwija sie do stalej,
// dla reszty do `(0.0 - x)`. Odtwarzamy to doslownie, bo od tego zalezy, czy
// wychodza te same liczby zmiennoprzecinkowe.
//
// Drzewo kompilujemy do postfiksu: formula liczy sie dla kazdego dziecka przy
// kazdym zejsciu, wiec chodzenie po wskaznikach byloby tu najdrozszym miejscem.
#pragma once

#include <cctype>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>

namespace md2 {

// Kolejnosc jak TERMINAL_ORDER w Pythonie.
constexpr int TERMINAL_COUNT = 11;
enum TerminalIndex {
    T_ST = 0, T_PE = 1, T_PD = 2, T_TO = 3, T_MTK = 4, T_MS = 5,
    T_JT = 6, T_HL = 7, T_TU = 8, T_TS = 9, T_IC = 10,
};

inline int terminal_index(const std::string& name) {
    if (name == "ST") return T_ST;
    if (name == "PE") return T_PE;
    if (name == "PD") return T_PD;
    if (name == "TO") return T_TO;
    if (name == "MTK") return T_MTK;
    if (name == "MS") return T_MS;
    if (name == "JT") return T_JT;
    if (name == "HL") return T_HL;
    if (name == "TU") return T_TU;
    if (name == "TS") return T_TS;
    if (name == "IC") return T_IC;
    if (name == "Rbar") return -1;  // statystyka wezla, nie stan gry
    throw std::runtime_error("Nieznana zmienna w formule: " + name);
}

enum OpCode : std::uint8_t {
    OP_CONST = 0, OP_VAR = 1, OP_RBAR = 2,
    OP_ADD = 3, OP_SUB = 4, OP_MUL = 5, OP_DIV = 6,
};

struct Instruction {
    std::uint8_t op;
    std::int8_t var;
    double value;
};

inline double protected_division(double numerator, double denominator) {
    return denominator != 0.0 ? numerator / denominator : 1.0;
}

class Program {
public:
    std::vector<Instruction> code;

    double eval(const double* terminals, double rbar) const {
        double stack[64];
        int top = 0;
        for (const Instruction& instruction : code) {
            switch (instruction.op) {
                case OP_CONST: stack[top++] = instruction.value; break;
                case OP_VAR: stack[top++] = terminals[instruction.var]; break;
                case OP_RBAR: stack[top++] = rbar; break;
                case OP_ADD: --top; stack[top - 1] = stack[top - 1] + stack[top]; break;
                case OP_SUB: --top; stack[top - 1] = stack[top - 1] - stack[top]; break;
                case OP_MUL: --top; stack[top - 1] = stack[top - 1] * stack[top]; break;
                default: --top; stack[top - 1] = protected_division(stack[top - 1], stack[top]); break;
            }
        }
        return stack[0];
    }
};

class Parser {
public:
    static Program compile(const std::string& text) {
        Parser parser(text);
        Program program;
        parser.parse_expr(program);
        parser.skip_spaces();
        if (parser.position_ != parser.text_.size()) {
            throw std::runtime_error("Nadmiarowe znaki w formule na pozycji " +
                                     std::to_string(parser.position_));
        }
        return program;
    }

private:
    explicit Parser(const std::string& text) : text_(text) {}

    const std::string& text_;
    std::size_t position_ = 0;

    void skip_spaces() {
        while (position_ < text_.size() && std::isspace(static_cast<unsigned char>(text_[position_]))) {
            ++position_;
        }
    }

    bool consume(char expected) {
        skip_spaces();
        if (position_ < text_.size() && text_[position_] == expected) {
            ++position_;
            return true;
        }
        return false;
    }

    char peek() {
        skip_spaces();
        return position_ < text_.size() ? text_[position_] : '\0';
    }

    void parse_expr(Program& program) {
        parse_term(program);
        for (;;) {
            char symbol = peek();
            if (symbol == '+' || symbol == '-') {
                ++position_;
                parse_term(program);
                program.code.push_back({symbol == '+' ? OP_ADD : OP_SUB, 0, 0.0});
            } else {
                return;
            }
        }
    }

    void parse_term(Program& program) {
        parse_factor(program);
        for (;;) {
            char symbol = peek();
            if (symbol == '*' || symbol == '/') {
                ++position_;
                parse_factor(program);
                program.code.push_back({symbol == '*' ? OP_MUL : OP_DIV, 0, 0.0});
            } else {
                return;
            }
        }
    }

    void parse_factor(Program& program) {
        char symbol = peek();
        if (symbol == '+') {
            ++position_;
            parse_factor(program);
            return;
        }
        if (symbol == '-') {
            ++position_;
            std::size_t mark = program.code.size();
            parse_factor(program);
            // Python zwija -stala do stalej, a reszte do (0.0 - x)
            if (program.code.size() == mark + 1 && program.code[mark].op == OP_CONST) {
                program.code[mark].value = -program.code[mark].value;
            } else {
                program.code.insert(program.code.begin() + static_cast<std::ptrdiff_t>(mark),
                                    {OP_CONST, 0, 0.0});
                program.code.push_back({OP_SUB, 0, 0.0});
            }
            return;
        }
        if (symbol == '(') {
            ++position_;
            parse_expr(program);
            if (!consume(')')) throw std::runtime_error("Brak nawiasu zamykajacego w formule");
            return;
        }
        if (std::isdigit(static_cast<unsigned char>(symbol)) || symbol == '.') {
            const char* start = text_.c_str() + position_;
            char* end = nullptr;
            double value = std::strtod(start, &end);
            if (end == start) throw std::runtime_error("Nieczytelna liczba w formule");
            position_ += static_cast<std::size_t>(end - start);
            program.code.push_back({OP_CONST, 0, value});
            return;
        }
        if (std::isalpha(static_cast<unsigned char>(symbol)) || symbol == '_') {
            std::size_t start = position_;
            while (position_ < text_.size() &&
                   (std::isalnum(static_cast<unsigned char>(text_[position_])) || text_[position_] == '_')) {
                ++position_;
            }
            std::string name = text_.substr(start, position_ - start);
            int index = terminal_index(name);
            if (index < 0) {
                program.code.push_back({OP_RBAR, 0, 0.0});
            } else {
                program.code.push_back({OP_VAR, static_cast<std::int8_t>(index), 0.0});
            }
            return;
        }
        throw std::runtime_error(std::string("Niedozwolony znak w formule: ") + symbol);
    }
};

}  // namespace md2
