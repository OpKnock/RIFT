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

def twin_demo():
    """Reproducible terminal demo of the Patient Digital Twin (synthetic data)."""
    from .health.demo_data import demo_stream
    from .health.ehr import demo_ehr, normalize_ehr
    from .health.evaluate import backtest
    from .health.twin import DigitalTwin

    ehr, _ = normalize_ehr(demo_ehr())
    twin = DigitalTwin(ehr, demo_stream())
    print("RIFT Patient Digital Twin — synthetic demo, decision support only")
    print(f"Patient {ehr.patient_id}: age {ehr.age:.0f}, {', '.join(ehr.conditions)}")
    for day in (0, 5, 9, 10, 11, 13):
        snap = twin.update(day)
        risk = snap["risk"]
        print(f"day {day:2d}: risk {risk['risk']:.2f} "
              f"{'EVENT' if risk['event_predicted'] else '     '} "
              f"quality {risk['input_quality']:.2f} "
              f"guardian {'PASS' if snap['guardian']['display_allowed'] else 'WITHHELD'}")
    report = backtest(DigitalTwin(ehr, demo_stream()), 7, 12)
    print(f"14-day backtest: agreement {report['event_agreement']:.2f}, "
          f"Brier {report['brier']:.3f}, coverage {report['interval_coverage']:.2f}")
    print("Full evidence (held-out, calibration, external): GET /api/twin/evidence")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("command",choices=["demo","twin-demo","serve"])
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=8080)
    args=parser.parse_args()
    if args.command=="demo": demo()
    elif args.command=="twin-demo": twin_demo()
    else: print(f"RIFT laboratory running at http://{args.host}:{args.port}"); serve(args.host,args.port)
if __name__=="__main__": main()
