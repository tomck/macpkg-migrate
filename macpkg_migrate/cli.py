import argparse,csv,json
from .catalog import fetch
from .inventory import all_managers
from .planner import make_plan

def main():
    parser=argparse.ArgumentParser(prog="macpkg-migrate"); sub=parser.add_subparsers(dest="command",required=True)
    plan=sub.add_parser("plan"); plan.add_argument("--output",default="macpkg-migration-plan.json"); plan.add_argument("--csv",default="macpkg-migration-preview.csv"); plan.add_argument("--refresh-catalog",action="store_true"); plan.add_argument("--preference",default="macports,fink,homebrew")
    args=parser.parse_args()
    installed=all_managers(); rows=make_plan(installed,fetch(refresh=args.refresh_catalog),tuple(args.preference.split(",")))
    open(args.output,"w").write(json.dumps(rows,indent=2)+"\n")
    with open(args.csv,"w",newline="") as stream:
        writer=csv.writer(stream); writer.writerow(["members","recommendation","manager","confidence","status","action"])
        for row in rows:
            choice=row.get("recommendation") or {}; writer.writerow([";".join(x["manager"]+":"+x["name"] for x in row["members"]),choice.get("name",""),choice.get("manager",""),choice.get("confidence",""),choice.get("status",""),row["action"]])
    print(f"Wrote {args.output} and {args.csv}; review the CSV before consolidating packages.")
