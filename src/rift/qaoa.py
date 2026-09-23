"""Dependency-free statevector QAOA simulator for small QUBOs.

This is a research/demo backend, not a claim of hardware advantage. It implements
the standard alternating cost-phase and X-mixer layers on a statevector and uses
a deterministic coordinate/grid search for variational parameters.
"""
from dataclasses import dataclass
from math import cos, exp, pi, sin
from .optimizer import QUBO, OptimizationResult
from .cvar import cvar_from_distribution

@dataclass(frozen=True)
class QAOAResult:
    assignment: dict[str, int]
    energy: float
    expected_energy: float
    probability: float
    depth: int
    iterations: int
    method: str
    angles: tuple[float, ...]

def _energies(qubo: QUBO) -> list[float]:
    n=len(qubo.variables)
    return [qubo.energy(dict(zip(qubo.variables, ((i>>j)&1 for j in range(n))))) for i in range(1<<n)]

def _apply_mixer(state: list[complex], n: int, beta: float) -> None:
    c=cos(beta); s=-1j*sin(beta)
    for q in range(n):
        step=1<<q
        for base in range(0,len(state),step*2):
            for j in range(step):
                a=base+j; b=a+step
                x,y=state[a],state[b]
                state[a]=c*x+s*y
                state[b]=s*x+c*y

def _state(energies: list[float], n: int, betas: tuple[float,...], gammas: tuple[float,...]) -> list[complex]:
    size=1<<n
    state=[1/(size**0.5) for _ in range(size)]
    for beta,gamma in zip(betas,gammas):
        for i,e in enumerate(energies):
            state[i] *= complex(cos(gamma*e), -sin(gamma*e))
        _apply_mixer(state,n,beta)
    return state

def _expectation(state:list[complex], energies:list[float])->float:
    return sum((abs(a)**2)*e for a,e in zip(state,energies))

def _cvar(state:list[complex], energies:list[float], alpha:float)->float:
    return cvar_from_distribution(energies,[abs(a)**2 for a in state],alpha)

def simulate_qaoa(qubo: QUBO, p:int=1, grid_steps:int=5, iterations:int=3, objective:str="expectation", alpha:float=0.25) -> QAOAResult:
    if not qubo.variables: raise ValueError("QUBO must contain at least one variable")
    if len(qubo.variables)>12: raise ValueError("Statevector simulator is limited to 12 qubits")
    if p<1 or grid_steps<2 or iterations<1: raise ValueError("Invalid QAOA configuration")
    if objective not in ("expectation","cvar"): raise ValueError("objective must be expectation or cvar")
    if not 0 < alpha <= 1: raise ValueError("alpha must be in (0,1]")
    energies=_energies(qubo); n=len(qubo.variables)
    betas=[pi/4]*p; gammas=[0.1]*p
    def score(bs,gs):
        state=_state(energies,n,tuple(bs),tuple(gs))
        return _expectation(state,energies) if objective=="expectation" else _cvar(state,energies,alpha)
    best=score(betas,gammas); evaluations=1
    for _ in range(iterations):
        for layer in range(p):
            for kind in ("beta","gamma"):
                current=betas if kind=="beta" else gammas
                center=current[layer]
                candidates=[(center + (k-grid_steps//2)*(pi/(2*grid_steps))) % pi for k in range(grid_steps)] if kind=="beta" else [(center + (k-grid_steps//2)*(2*pi/grid_steps)) % (2*pi) for k in range(grid_steps)]
                local_best=(best,center)
                for value in candidates:
                    trial=current[:]; trial[layer]=value
                    val=score(trial,gammas) if kind=="beta" else score(betas,trial)
                    evaluations+=1
                    if val<local_best[0]: local_best=(val,value)
                best=local_best[0]; current[layer]=local_best[1]
    state=_state(energies,n,tuple(betas),tuple(gammas))
    probabilities=[abs(a)**2 for a in state]
    idx=min(range(len(energies)),key=lambda i: energies[i])
    # Report the most probable measured state, plus its exact energy.
    measured=max(range(len(probabilities)),key=lambda i: probabilities[i])
    assignment=dict(zip(qubo.variables,((measured>>j)&1 for j in range(n))))
    return QAOAResult(assignment,energies[measured],best,probabilities[measured],p,evaluations,"qaoa-statevector-simulator",tuple(betas+gammas))

def qaoa_minimize(qubo:QUBO, p:int=1, grid_steps:int=5, iterations:int=3, objective:str="expectation", alpha:float=0.25)->OptimizationResult:
    r=simulate_qaoa(qubo,p,grid_steps,iterations,objective,alpha)
    return OptimizationResult(r.assignment,r.energy,r.method)
