#!/usr/bin/env python3
"""Pinned duration-fix scope, retaining the original executable/PCM/ABI checks.

The C1/package audit is unchanged. This entrypoint names a new two-file scope,
then reuses its strict old-client, export and complete-grid comparison functions.
"""
import argparse
import json
from pathlib import Path
import audit as a
import duration_scope


def run(args):
    if args.output.exists():
        raise ValueError('new output directory required')
    base, donor, current, package, reference, host = [p.resolve(strict=True) for p in (
        args.baseline_source, args.donor_source, args.source, args.package_reference_source,
        args.duration_reference_source, args.host_reference_source)]
    libs={k:getattr(args,k+'_library').resolve(strict=True) for k in ('original','off','on')}
    clients={k:getattr(args,k+'_client').resolve(strict=True) for k in ('c','cpp')}
    tracked=[*libs.values(),*clients.values(),args.donor_replay,args.candidate_replay,
             Path(__file__),Path(a.__file__),Path(duration_scope.__file__)]
    files={str(p):a.sha(p) for p in tracked}
    def scope():return duration_scope.source_contract(base,donor,current,package,reference,host)
    formant_reference=getattr(args,'formant_reference_source',None)
    if formant_reference is not None:
        import formant_scope
        formant_reference=formant_reference.resolve(strict=True)
        scope=lambda:formant_scope.source_contract(base,donor,current,package,reference,formant_reference,host)
        files[str(Path(formant_scope.__file__))]=a.sha(Path(formant_scope.__file__))
    ring_reference=getattr(args,'ring_reference_source',None)
    if ring_reference is not None:
        if formant_reference is None:raise ValueError('ring scope requires formant predecessor')
        import ring_scope
        ring_reference=ring_reference.resolve(strict=True)
        scope=lambda:ring_scope.source_contract(base,donor,current,package,reference,formant_reference,ring_reference,host)
        files[str(Path(ring_scope.__file__))]=a.sha(Path(ring_scope.__file__))
    fft_reference=getattr(args,'fft_stage_reference_source',None)
    if fft_reference is not None:
        if ring_reference is None:raise ValueError('FFT-stage scope requires ring predecessor')
        import fft_stage_scope
        fft_reference=fft_reference.resolve(strict=True)
        scope=lambda:fft_stage_scope.source_contract(base,donor,current,package,reference,formant_reference,ring_reference,fft_reference,host)
        files[str(Path(fft_stage_scope.__file__))]=a.sha(Path(fft_stage_scope.__file__))
    four_reference=getattr(args,'fft_four_reference_source',None)
    if four_reference is not None:
        if fft_reference is None:raise ValueError('FFT-four scope requires first-stage predecessor')
        import fft_four_scope
        four_reference=four_reference.resolve(strict=True)
        scope=lambda:fft_four_scope.source_contract(base,donor,current,package,reference,formant_reference,ring_reference,fft_reference,four_reference,host)
        files[str(Path(fft_four_scope.__file__))]=a.sha(Path(fft_four_scope.__file__))
    checked=scope()
    args.output.mkdir(parents=True)
    (args.output/'plan.json').write_text(json.dumps(dict(files=files,sources=checked),indent=2)+'\n')
    old_exports=a.exports(libs['original'])
    for name in ('off','on'):a.export_contract(old_exports,a.exports(libs[name]))
    counts={}
    for kind,client in clients.items():
        for name,lib in libs.items():a.execute(client,lib,args.output/f'{kind}-{name}.csv')
        counts[kind]={name:a.compare(args.output/f'{kind}-original.csv',args.output/f'{kind}-{name}.csv',kind)
                      for name in ('off','on')}
    records=a.read_grid(args.output/'c-original.csv','c')
    for key,value in records.items():
        if key[-1]==32 and value!=records[(*key[:-1],257)]:
            raise ValueError('legacy block partition changed')
    preview=a.compare(args.donor_replay,args.candidate_replay,'preview')
    if checked!=scope():raise ValueError('source changed during audit')
    for name,digest in files.items():
        if a.sha(Path(name))!=digest:raise ValueError('binary/evidence changed during audit')
    report=dict(schema='boiled-egg.sdk-duration-compatibility.v1',**checked,
                legacy_pairs=counts,legacy_partition_pairs=144,preview_pairs=preview,
                previous_exports=sorted(old_exports),added_exports=sorted(a.ADDITIONS),files=files,
                evidence_sha256={p.name:a.sha(p) for p in args.output.iterdir() if p.is_file()},
                notes='The unchanged old executables and full CSVs are compared, not whitelisted outputs.')
    (args.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-source','donor-source','source','package-reference-source',
                 'duration-reference-source','host-reference-source','original-library','off-library',
                 'on-library','c-client','cpp-client','donor-replay','candidate-replay','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--formant-reference-source',type=Path,help='Pinned post-duration source; exact three-file formant-option scope')
    p.add_argument('--ring-reference-source',type=Path,help='Pinned post-formant source; exact ring-address replacement scope')
    p.add_argument('--fft-stage-reference-source',type=Path,help='Pinned post-ring source; exact first-stage FFT edit')
    p.add_argument('--fft-four-reference-source',type=Path,help='Pinned post-first-stage source; exact length-four FFT edit')
    r=run(p.parse_args())
    print(json.dumps({k:r[k] for k in ('legacy_pairs','preview_pairs','runtime_files','protected_files')}))
