// MT19937 zgodny bit w bit z `random.Random` z CPythona.
//
// Port jest bezwartosciowy, jesli nie odtwarza losowosci Pythona: te same
// sekwencje akcji musza wychodzic z obu implementacji, inaczej test roznicowy
// moze porownywac tylko rozklady. Odtwarzamy wiec trzy rzeczy:
//
//   * `init_by_array` z seedem rozbitym na 32-bitowe slowa (CPython
//     `random_seed`: dla int bierze wartosc bezwzgledna, keyused = max(1,
//     ceil(bits/32)));
//   * `getrandbits(k)` = `genrand_uint32() >> (32 - k)` dla k <= 32;
//   * `_randbelow_with_getrandbits(n)`: k = n.bit_length(), losuj k bitow,
//     powtarzaj przy r >= n (odrzucanie, nie modulo).
//
// `choice(seq)` w CPythonie to `seq[_randbelow(len(seq))]`, wiec wystarczy
// `randbelow`.
#pragma once

#include <cstdint>
#include <vector>

namespace md2 {

class PyRandom {
public:
    explicit PyRandom(std::uint64_t seed) { seed_from_int(seed); }

    // CPython: init_by_array na slowach 32-bitowych wartosci bezwzglednej
    void seed_from_int(std::uint64_t seed) {
        std::vector<std::uint32_t> key;
        if (seed == 0) {
            key.push_back(0u);  // bits == 0 -> keyused == 1
        } else {
            std::uint64_t rest = seed;
            while (rest != 0) {
                key.push_back(static_cast<std::uint32_t>(rest & 0xffffffffu));
                rest >>= 32;
            }
        }
        init_by_array(key);
    }

    std::uint32_t genrand_uint32() {
        if (index_ >= N) {
            generate();
        }
        std::uint32_t y = state_[index_++];
        y ^= (y >> 11);
        y ^= (y << 7) & 0x9d2c5680u;
        y ^= (y << 15) & 0xefc60000u;
        y ^= (y >> 18);
        return y;
    }

    // getrandbits(k) dla 1 <= k <= 32
    std::uint32_t getrandbits(int k) { return genrand_uint32() >> (32 - k); }

    // _randbelow_with_getrandbits
    std::uint32_t randbelow(std::uint32_t n) {
        if (n == 0) {
            return 0;
        }
        int k = bit_length(n);
        std::uint32_t r = getrandbits(k);
        while (r >= n) {
            r = getrandbits(k);
        }
        return r;
    }

private:
    static constexpr int N = 624;
    static constexpr int M = 397;
    static constexpr std::uint32_t MATRIX_A = 0x9908b0dfu;
    static constexpr std::uint32_t UPPER_MASK = 0x80000000u;
    static constexpr std::uint32_t LOWER_MASK = 0x7fffffffu;

    std::uint32_t state_[N] = {0};
    int index_ = N + 1;

    static int bit_length(std::uint32_t value) {
        int bits = 0;
        while (value) {
            ++bits;
            value >>= 1;
        }
        return bits;
    }

    void init_genrand(std::uint32_t s) {
        state_[0] = s;
        for (int i = 1; i < N; ++i) {
            state_[i] = static_cast<std::uint32_t>(
                1812433253u * (state_[i - 1] ^ (state_[i - 1] >> 30)) + static_cast<std::uint32_t>(i));
        }
        index_ = N;
    }

    void init_by_array(const std::vector<std::uint32_t>& key) {
        init_genrand(19650218u);
        int i = 1;
        int j = 0;
        int k = N > static_cast<int>(key.size()) ? N : static_cast<int>(key.size());
        for (; k; --k) {
            state_[i] = (state_[i] ^ ((state_[i - 1] ^ (state_[i - 1] >> 30)) * 1664525u)) + key[j] +
                        static_cast<std::uint32_t>(j);
            ++i;
            ++j;
            if (i >= N) {
                state_[0] = state_[N - 1];
                i = 1;
            }
            if (j >= static_cast<int>(key.size())) {
                j = 0;
            }
        }
        for (k = N - 1; k; --k) {
            state_[i] = (state_[i] ^ ((state_[i - 1] ^ (state_[i - 1] >> 30)) * 1566083941u)) -
                        static_cast<std::uint32_t>(i);
            ++i;
            if (i >= N) {
                state_[0] = state_[N - 1];
                i = 1;
            }
        }
        state_[0] = 0x80000000u;
        index_ = N;
    }

    void generate() {
        static const std::uint32_t mag01[2] = {0x0u, MATRIX_A};
        int kk = 0;
        for (; kk < N - M; ++kk) {
            std::uint32_t y = (state_[kk] & UPPER_MASK) | (state_[kk + 1] & LOWER_MASK);
            state_[kk] = state_[kk + M] ^ (y >> 1) ^ mag01[y & 0x1u];
        }
        for (; kk < N - 1; ++kk) {
            std::uint32_t y = (state_[kk] & UPPER_MASK) | (state_[kk + 1] & LOWER_MASK);
            state_[kk] = state_[kk + (M - N)] ^ (y >> 1) ^ mag01[y & 0x1u];
        }
        std::uint32_t y = (state_[N - 1] & UPPER_MASK) | (state_[0] & LOWER_MASK);
        state_[N - 1] = state_[M - 1] ^ (y >> 1) ^ mag01[y & 0x1u];
        index_ = 0;
    }
};

}  // namespace md2
