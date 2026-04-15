"""
ga_optimizer.py
---------------
Binary-coded GA — mirrors MATLAB implementation.

Genes: vg_idx (discrete) | n (continuous)
T_op is fixed — NOT a gene.

Encoding    : binary, 2 decimal places
Selection   : SUS
Crossover   : uniform with binary mask
Mutation    : flip-bit per bit
Elitism     : top N_elite carried unchanged
Penalty     : Hadj-Alouane & Bean adaptive lambda
Merit       : C_MAX - Aval  (higher = better)
"""
from __future__ import annotations

import math
import random
from typing import Callable

from genetic_algorithm.fitness import C_MAX, VG_GRADES


# ---------------------------------------------------------------------------
# Encode / decode
# ---------------------------------------------------------------------------

def _n_bits(lo: float, hi: float, decimals: int = 2) -> int:
    n_vals = int(round((hi - lo) * (10 ** decimals))) + 1
    return max(1, math.ceil(math.log2(max(n_vals, 2))))


def _encode_gene(value: float, lo: float, hi: float, n: int) -> list:
    max_int = (1 << n) - 1
    scaled  = int(round((value - lo) / (hi - lo) * max_int))
    scaled  = max(0, min(scaled, max_int))
    return [(scaled >> (n - 1 - i)) & 1 for i in range(n)]


def _decode_gene(bits: list, lo: float, hi: float) -> float:
    n       = len(bits)
    max_int = (1 << n) - 1
    val_int = sum(b << (n - 1 - i) for i, b in enumerate(bits))
    return lo + (hi - lo) * val_int / max_int


def _encode_individual(genes: dict, bounds: dict, bit_lengths: dict) -> list:
    chrom = []
    for gene in sorted(bounds.keys()):
        lo, hi = bounds[gene]
        chrom += _encode_gene(genes[gene], lo, hi, bit_lengths[gene])
    return chrom


def _decode_individual(chrom: list, bounds: dict, bit_lengths: dict) -> dict:
    genes = {}
    idx   = 0
    for gene in sorted(bounds.keys()):
        lo, hi = bounds[gene]
        n       = bit_lengths[gene]
        bits    = chrom[idx: idx + n]
        val     = _decode_gene(bits, lo, hi)
        if gene == "vg_idx":
            val = int(round(val))
            val = max(0, min(val, len(VG_GRADES) - 1))
        genes[gene] = val
        idx += n
    return genes


# ---------------------------------------------------------------------------
# Genetic operators
# ---------------------------------------------------------------------------

def _sus_selection(merits: list, n_select: int) -> list:
    """Stochastic Universal Sampling — mirrors MATLAB sus_selection."""
    total = sum(merits)
    if total <= 0:
        return [random.randint(0, len(merits) - 1) for _ in range(n_select)]
    ptr_dist = total / n_select
    start    = random.uniform(0, ptr_dist)
    pointers = [start + i * ptr_dist for i in range(n_select)]
    selected = []
    cumsum, j = 0.0, 0
    for ptr in pointers:
        while cumsum + merits[j] < ptr:
            cumsum += merits[j]
            j = (j + 1) % len(merits)
        selected.append(j)
    return selected


def _uniform_crossover(p1: list, p2: list, p_cross: float) -> tuple:
    """Uniform crossover with binary mask — mirrors MATLAB crossover_function."""
    if random.random() > p_cross:
        return p1[:], p2[:]
    lc   = len(p1)
    mask = [random.randint(0, 1) for _ in range(lc)]
    c1   = [p1[i] if mask[i] == 0 else p2[i] for i in range(lc)]
    c2   = [p2[i] if mask[i] == 0 else p1[i] for i in range(lc)]
    return c1, c2


def _flip_bit_mutation(chrom: list, p_mut: float) -> list:
    """Flip-bit mutation — mirrors MATLAB mutacao."""
    return [1 - b if random.random() < p_mut else b for b in chrom]


# ---------------------------------------------------------------------------
# Optimiser
# ---------------------------------------------------------------------------

class GeneticOptimiser:
    def __init__(
        self,
        fitness_fn: Callable,
        fitness_kwargs: dict,
        bounds: dict,
        pop_size: int = 30,
        elite_frac: float = 0.30,
        P_cross: float = 0.90,
        P_mut: float = 0.008,
        max_gen: int = 100,
        lambda_init: float = 10.0,
        beta1: float = 1.2,
        beta2: float = 1.1,
        Nf: int = 20,
        seed: int | None = 42,
        verbose: bool = True,
    ):
        self.fitness_fn      = fitness_fn
        self.fitness_kwargs  = fitness_kwargs
        self.bounds          = bounds
        self.pop_size        = pop_size
        self.N_elite         = max(1, int(round(pop_size * elite_frac)))
        self.P_cross         = P_cross
        self.P_mut           = P_mut
        self.max_gen         = max_gen
        self.lam             = lambda_init
        self.beta1           = beta1
        self.beta2           = beta2
        self.Nf              = Nf
        self.verbose         = verbose

        if seed is not None:
            random.seed(seed)

        self.bit_lengths = {}
        for gene, (lo, hi) in bounds.items():
            if gene == "vg_idx":
                self.bit_lengths[gene] = _n_bits(lo, hi, decimals=0)
            else:
                self.bit_lengths[gene] = _n_bits(lo, hi, decimals=2)

        self.chrom_len  = sum(self.bit_lengths.values())
        self._gene_order = sorted(bounds.keys())

    def run(self) -> dict:
        # ---- init ----
        pop = [[random.randint(0, 1) for _ in range(self.chrom_len)]
               for _ in range(self.pop_size)]

        history, pen_history, lambda_history = [], [], []
        best_chrom = pop[0][:]
        best_Aval  = C_MAX - 1e-6
        best_merit = 1e-9

        conta_top_zero     = 0
        conta_top_non_zero = 0
        prev_pen           = None

        for k in range(1, self.max_gen + 1):

            avals, pens, merits = self._evaluate_pop(pop)
            order   = sorted(range(self.pop_size),
                             key=lambda i: merits[i], reverse=True)
            best_i  = order[0]
            cur_pen = pens[best_i]

            if merits[best_i] > best_merit:
                best_merit = merits[best_i]
                best_Aval  = avals[best_i]
                best_chrom = pop[best_i][:]

            history.append(merits[best_i])
            pen_history.append(cur_pen)
            lambda_history.append(self.lam)

            # ---- Hadj-Alouane & Bean lambda update (exact MATLAB logic) ----
            # Use threshold for float comparison — pen < eps counts as zero
            _eps_pen = 1e-9
            cur_zero  = cur_pen  < _eps_pen
            prev_zero = (prev_pen < _eps_pen) if prev_pen is not None else None

            if prev_pen is None:
                if cur_zero:
                    conta_top_zero     = 1
                else:
                    conta_top_non_zero = 1
            else:
                if not cur_zero and not prev_zero:
                    conta_top_non_zero += 1
                elif not cur_zero and prev_zero:
                    conta_top_non_zero  = 1;  conta_top_zero = 0
                elif cur_zero and prev_zero:
                    conta_top_zero     += 1
                elif cur_zero and not prev_zero:
                    conta_top_zero      = 1;  conta_top_non_zero = 0

            prev_pen = cur_pen  # raw value kept for next iteration threshold check

            if conta_top_non_zero >= self.Nf:
                self.lam           *= self.beta1
                conta_top_non_zero  = 0
                avals, pens, merits = self._evaluate_pop(pop)
                order = sorted(range(self.pop_size),
                               key=lambda i: merits[i], reverse=True)

            elif conta_top_zero >= self.Nf:
                self.lam        = max(self.lam / self.beta2, 1e-6)
                conta_top_zero  = 0
                avals, pens, merits = self._evaluate_pop(pop)
                order = sorted(range(self.pop_size),
                               key=lambda i: merits[i], reverse=True)

            # ---- progress ----
            if self.verbose and (k % 10 == 0 or k == 1):
                g = _decode_individual(pop[order[0]], self.bounds, self.bit_lengths)
                print(f"    Gen {k:3d}/{self.max_gen} | "
                      f"merit={merits[order[0]]:.4f} | "
                      f"λ={self.lam:.3f} | pen={pens[order[0]]:.5f} | "
                      f"VG={VG_GRADES[g['vg_idx']]}  n={g['n']:.0f}rpm")

            # ---- elitism ----
            elite = [pop[order[i]][:] for i in range(self.N_elite)]

            # ---- SUS + crossover + mutation ----
            # SUS selects N_pop parents (full population size, like MATLAB)
            # then shuffle before pairing — mirrors MATLAB "baralhar conjunto acasalamento"
            n_offspring = self.pop_size - self.N_elite
            sel_idx  = _sus_selection(merits, self.pop_size)
            parents  = [pop[i] for i in sel_idx]
            random.shuffle(parents)   # shuffle before pairing

            offspring = []
            i = 0
            while len(offspring) < n_offspring:
                p1 = parents[i % len(parents)]
                p2 = parents[(i + 1) % len(parents)]
                c1, c2 = _uniform_crossover(p1, p2, self.P_cross)
                offspring.append(_flip_bit_mutation(c1, self.P_mut))
                if len(offspring) < n_offspring:
                    offspring.append(_flip_bit_mutation(c2, self.P_mut))
                i += 2

            pop = elite + offspring[:n_offspring]

        best_genes = _decode_individual(best_chrom, self.bounds, self.bit_lengths)
        return {
            "best_genes"    : best_genes,
            "best_Aval"     : best_Aval,
            "best_merit"    : best_merit,
            "history"       : history,
            "pen_history"   : pen_history,
            "lambda_history": lambda_history,
        }

    def _evaluate_pop(self, pop):
        avals, pens, merits = [], [], []
        for chrom in pop:
            genes     = _decode_individual(chrom, self.bounds, self.bit_lengths)
            Aval, pen = self.fitness_fn(genes, lam=self.lam, **self.fitness_kwargs)
            Aval      = min(Aval, C_MAX - 1e-6)
            merit     = max(C_MAX - Aval, 1e-9)
            avals.append(Aval);  pens.append(pen);  merits.append(merit)
        return avals, pens, merits