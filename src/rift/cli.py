import argparse
from .api import serve
from .counterfactual import generate_futures
from .robust import rank_robust_candidates
from .scenarios import emergency_building

def demo():
    scenario=emergency_building(); futures=generate_futures(scenario)
    perturbations=[{"smoke":2.0},{"crowd":80.0},{"smoke":2.0,"crowd":80.0},{"corridor_capacity":-70.0}]
    ranked=rank_robust_candidates(scenario,futures,perturbations)
    print("RIFT — Robust Intervention & Future Testing")
    print(f"Futures explored: {len(futures)}")
    for item in ranked[:3]:
        worst=item.worst_case.adversarial_score if item.worst_case else item.candidate.score
        print("Policy:",item.candidate.policy,"score:",round(item.candidate.score,2),"worst:",round(worst,2))
    print("Guardian-ready candidates:",len(ranked))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["demo","serve"])
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8080)
    args=parser.parse_args()
    if args.command=="demo": demo()
    else: print(f"RIFT laboratory running at http://{args.host}:{args.port}"); serve(args.host,args.port)
if __name__=="__main__": main()
