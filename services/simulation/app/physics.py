"""Real numerics for the quartic anharmonic oscillator, H = H0 + lambda * x^4
(hbar = m = omega = 1). No mock data: the ladder-operator matrix elements and
the diagonalization are actually computed with numpy.
"""

import numpy as np


def build_position_operator(n_basis: int) -> np.ndarray:
    """x = (a + a^dagger) / sqrt(2) in the truncated number basis."""
    a = np.zeros((n_basis, n_basis))
    for n in range(1, n_basis):
        a[n - 1, n] = np.sqrt(n)
    a_dag = a.T
    return (a + a_dag) / np.sqrt(2)


def diagonalize(lam: float, n_basis: int) -> np.ndarray:
    x = build_position_operator(n_basis)
    x4 = x @ x @ x @ x
    h0 = np.diag(np.arange(n_basis) + 0.5)
    h = h0 + lam * x4
    eigenvalues = np.linalg.eigvalsh(h)
    return np.sort(eigenvalues)


def perturbative_estimate(lam: float) -> dict[str, float]:
    """Rayleigh-Schrodinger perturbation theory to second order for the ground state."""
    zeroth = 0.5
    first_order = zeroth + 0.75 * lam
    second_order = first_order - (21.0 / 8.0) * lam**2
    return {
        "zeroth_order": zeroth,
        "first_order": first_order,
        "second_order": second_order,
    }


def run_simulation(lam: float, n_basis: int) -> dict:
    if n_basis < 8:
        raise ValueError("n_basis must be at least 8 for a meaningful truncation")

    spectrum = diagonalize(lam, n_basis)
    ground_state_numerical = float(spectrum[0])
    estimate = perturbative_estimate(lam)

    difference_pct = (
        abs(ground_state_numerical - estimate["second_order"]) / estimate["second_order"] * 100
    )

    return {
        "lambda": lam,
        "basis_size": n_basis,
        "perturbative": estimate,
        "numerical_ground_state": ground_state_numerical,
        "numerical_low_lying_levels": [float(v) for v in spectrum[:5]],
        "agreement_pct_difference": difference_pct,
    }
