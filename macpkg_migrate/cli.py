import argparse,csv,json,subprocess
from .catalog import fetch
from .inventory import all_managers
from .planner import make_plan

GUIDE='''macpkg-migrate — Homebrew, MacPorts, and Fink consolidation planner

Safe workflow:
  1. Inventory: macpkg-migrate inventory
  2. Plan: macpkg-migrate plan --output macpkg-migration-plan.json --csv macpkg-migration-preview.csv
  3. Dry run: macpkg-migrate migrate --plan macpkg-migration-plan.json
  4. Apply after review: macpkg-migrate migrate --plan macpkg-migration-plan.json --install

Use --preference fink,macports,homebrew to choose a preferred owner.
Near-hits and ambiguous mappings always require review. No manager is removed automatically.
'''

def main():
    parser=argparse.ArgumentParser(prog='macpkg-migrate'); sub=parser.add_subparsers(dest='command')
    sub.add_parser('inventory')
    plan=sub.add_parser('plan'); plan.add_argument('--output',default='macpkg-migration-plan.json'); plan.add_argument('--csv',default='macpkg-migration-preview.csv'); plan.add_argument('--refresh-catalog',action='store_true'); plan.add_argument('--preference',default='macports,fink,homebrew')
    migrate=sub.add_parser('migrate'); migrate.add_argument('--plan',required=True); migrate.add_argument('--install',action='store_true'); migrate.add_argument('--yes',action='store_true')
    verify=sub.add_parser('verify'); verify.add_argument('--plan',required=True)
    args=parser.parse_args()
    if args.command is None: print(GUIDE); return
    if args.command=='inventory': print(json.dumps(all_managers(),indent=2)); return
    if args.command=='plan':
        installed=all_managers(); rows=make_plan(installed,fetch(installed),tuple(args.preference.split(',')))
        open(args.output,'w').write(json.dumps(rows,indent=2)+'\n')
        with open(args.csv,'w',newline='') as stream:
            writer=csv.writer(stream); writer.writerow(['members','recommendation','manager','confidence','status','action'])
            for row in rows:
                choice=row.get('recommendation') or {}; writer.writerow([';'.join(x['manager']+':'+x['name'] for x in row['members']),choice.get('name',''),choice.get('manager',''),choice.get('confidence',''),choice.get('status',''),row['action']])
        print(f'Wrote {args.output} and {args.csv}; review the CSV before consolidating packages.'); return
    rows=json.load(open(args.plan))
    if args.command=='verify': print(json.dumps({'status':'review-required','groups':len(rows),'message':'Re-run inventory and compare installed managers after applying the reviewed plan.'},indent=2)); return
    apply=args.install and (args.yes or input('Apply reviewed multi-manager migration? [y/N] ').strip().lower() in ('y','yes')); results=[]
    for row in rows:
        choice=row.get('recommendation') or {}; status='needs-review'
        if apply and row.get('action')=='consolidate' and choice.get('manager') in ('fink','macports'):
            outcome=subprocess.run(['fink' if choice['manager']=='fink' else 'port','install',choice['name']]); status='installed' if outcome.returncode==0 else 'failed'
        elif not apply: status='dry-run'
        results.append({**row,'status':status})
    print(json.dumps(results,indent=2))
