import argparse,csv,json,subprocess,sys
from .binaries import ensure_binaries
from .catalog import fetch
from .inventory import all_managers
from .planner import make_plan

GUIDE='''macpkg-migrate — Homebrew, MacPorts, and Fink consolidation planner

Safe workflow:
  1. Inventory: macpkg-migrate inventory
  2. Plan: macpkg-migrate plan --output macpkg-migration-plan.json --csv macpkg-migration-preview.csv
  3. Dry run: macpkg-migrate migrate --plan macpkg-migration-plan.json
  4. Apply after review: macpkg-migrate migrate --plan macpkg-migration-plan.json --install
  5. Check results: macpkg-migrate verify --plan macpkg-migration-plan.json

Use --preference fink,macports,homebrew to choose a preferred owner.
Near-hits and ambiguous mappings always require review. No manager is removed automatically.
Only MacPorts and Fink targets are installed; Homebrew targets are reported, never installed.
Requires the catalog client: brew tap tomck/escapefrombrewyork && brew install macpkgmap
'''

def main():
    parser=argparse.ArgumentParser(prog='macpkg-migrate'); sub=parser.add_subparsers(dest='command')
    sub.add_parser('inventory')
    plan=sub.add_parser('plan'); plan.add_argument('--output',default='macpkg-migration-plan.json'); plan.add_argument('--csv',default='macpkg-migration-preview.csv'); plan.add_argument('--preference',default='macports,fink,homebrew')
    migrate=sub.add_parser('migrate'); migrate.add_argument('--plan',required=True); migrate.add_argument('--install',action='store_true'); migrate.add_argument('--yes',action='store_true')
    verify=sub.add_parser('verify'); verify.add_argument('--plan',required=True)
    args=parser.parse_args()
    if args.command is None: print(GUIDE); return
    if args.command=='inventory': print(json.dumps(all_managers(),indent=2)); return
    if args.command=='plan':
        progress=lambda message: print(message,file=sys.stderr)
        try:
            installed=all_managers()
            relations=ensure_binaries(fetch(installed,progress=progress),progress=progress)
            rows=make_plan(installed,relations)
        except RuntimeError as exc:
            print(f"macpkg-migrate: error: {exc}",file=sys.stderr); raise SystemExit(1)
        builds=[(row.get("recommendation") or {}).get("name","?") for row in rows if row.get("action")=="consolidate" and (row.get("recommendation") or {}).get("install_method")=="source"]
        if builds: progress(f"Warning: {len(builds)} recommendation(s) would build from source: {', '.join(builds)}")
        open(args.output,'w').write(json.dumps(rows,indent=2)+'\n')
        with open(args.csv,'w',newline='') as stream:
            writer=csv.writer(stream); writer.writerow(['members','recommendation','manager','confidence','status','action'])
            for row in rows:
                choice=row.get('recommendation') or {}; writer.writerow([';'.join(x['manager']+':'+x['name'] for x in row['members']),choice.get('name',''),choice.get('manager',''),choice.get('confidence',''),choice.get('status',''),row['action']])
        print(f'Wrote {args.output} and {args.csv}; review the CSV before consolidating packages.'); return
    rows=json.load(open(args.plan))
    if args.command=='verify':
        current={(x.get("manager"),x.get("type"),x.get("name")) for x in all_managers()}
        groups=[]
        for row in rows:
            choice=row.get("recommendation") or {}
            key=(choice.get("manager"),choice.get("type"),choice.get("name"))
            installed=key in current
            groups.append({"members":row.get("members",[]),"recommendation":choice,"installed":installed,"status":"verified" if installed else "pending"})
        print(json.dumps(groups,indent=2)); return
    apply=args.install and (args.yes or input('Apply reviewed multi-manager migration? [y/N] ').strip().lower() in ('y','yes')); results=[]
    for row in rows:
        choice=row.get('recommendation') or {}; status='needs-review'
        if apply and row.get('action')=='consolidate' and choice.get('manager') in ('fink','macports'):
            outcome=subprocess.run(['fink' if choice['manager']=='fink' else 'port','install',choice['name']]); status='installed' if outcome.returncode==0 else 'failed'
        elif not apply: status='dry-run'
        results.append({**row,'status':status})
    print(json.dumps(results,indent=2))
