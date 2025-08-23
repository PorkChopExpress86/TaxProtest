from __future__ import annotations
from typing import List, Dict, Any

def compute_pricing_stats(subject: Dict[str, Any], comps: List[Dict[str, Any]]) -> Dict[str, Any]:
    import math
    stats: Dict[str, Any] = {}
    values = [float(c['market_value']) for c in comps if c.get('market_value') not in (None,'','0')]
    ppsf_list = [float(c['ppsf']) for c in comps if c.get('ppsf') not in (None,'','0')]
    def basic(series: List[float]) -> Dict[str, Any]:
        if not series: return {'count':0}
        s=sorted(series); n=len(s); mean=sum(s)/n
        med = s[n//2] if n%2==1 else (s[n//2-1]+s[n//2])/2
        q1=s[int(0.25*(n-1))]; q3=s[int(0.75*(n-1))]; iqr=q3-q1; rng=s[-1]-s[0]
        var = sum((x-mean)**2 for x in s)/n if n>0 else 0; std=math.sqrt(var); cv=(std/mean) if mean else None
        return {'count':n,'mean':round(mean,2),'median':round(med,2),'min':round(s[0],2),'max':round(s[-1],2),'q1':round(q1,2),'q3':round(q3,2),'iqr':round(iqr,2),'range':round(rng,2),'std':round(std,2),'cv':round(cv,3) if cv is not None else None}
    stats['value_stats']=basic(values); stats['ppsf_stats']=basic(ppsf_list)
    subj_val=subject.get('market_value'); subj_ppsf=subject.get('ppsf')
    def subj_vs(val, base):
        if val is None or not base or base.get('count',0)==0: return {}
        out: Dict[str, Any] = {}
        try: fval=float(val)
        except Exception: return {}
        for k in ['mean','median']:
            basev=base.get(k)
            if basev:
                out[f'diff_vs_{k}']=round(fval-basev,2)
                out[f'pct_vs_{k}']=round(((fval-basev)/basev)*100,2) if basev else None
        return out
    stats['subject_vs_value']=subj_vs(subj_val, stats['value_stats'])
    stats['subject_vs_ppsf']=subj_vs(subj_ppsf, stats['ppsf_stats'])
    if subj_ppsf and ppsf_list:
        try:
            subj_ppsf_f=float(subj_ppsf)
            def within(pct: float)->int:
                lo=subj_ppsf_f*(1-pct); hi=subj_ppsf_f*(1+pct); return sum(1 for x in ppsf_list if lo<=x<=hi)
            stats['ppsf_band_counts']={'within_5pct':within(0.05),'within_10pct':within(0.10),'within_15pct':within(0.15)}
        except Exception: pass
    pools=[c.get('has_pool') for c in comps if c.get('has_pool') in (0,1)]
    garages=[c.get('has_garage') for c in comps if c.get('has_garage') in (0,1)]
    if pools and subject.get('has_pool') in (0,1):
        try:
            subj_pool = int(subject['has_pool'])
            stats['pool_match_rate']=round(sum(1 for p in pools if p is not None and int(p)==subj_pool)/len(pools)*100,2)
        except Exception:
            pass
    if garages and subject.get('has_garage') in (0,1):
        try:
            subj_gar = int(subject['has_garage'])
            stats['garage_match_rate']=round(sum(1 for g in garages if g is not None and int(g)==subj_gar)/len(garages)*100,2)
        except Exception:
            pass
    if stats['ppsf_stats'].get('count',0) >= 4:
        try:
            q1=stats['ppsf_stats']['q1']; q3=stats['ppsf_stats']['q3']; iqr=stats['ppsf_stats']['iqr']
            lo=q1-1.5*iqr; hi=q3+1.5*iqr; trimmed=[x for x in ppsf_list if lo<=x<=hi]
            if trimmed and trimmed!=ppsf_list: stats['trimmed_ppsf_median']=basic(trimmed)['median']
        except Exception: pass
    return stats
