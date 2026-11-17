"""Conferência dos dados do mapa (site/data/): contas de consistência entre os arquivos, sem baixar nada.

Confere se os municípios somam o estado, se os totais batem, se as partes somam o todo e se os pontos caem dentro
do Brasil. Não substitui a conferência com a fonte; serve para pegar erro de conta ou arquivo pela metade.
Uso: python scripts/conferir_dados.py [--registro]   (sai com erro se achar alguma diferença; com --registro, grava o
resultado em site/data/conferencia.json; no robô mensal roda depois dos robôs do mapa, só como aviso)
Criado na conferência de 16/11/2026. Só usa a biblioteca padrão.
"""
import json, collections, sys
from pathlib import Path
D=str(Path(__file__).resolve().parents[1]/'site'/'data')+'/'
J=lambda f: json.load(open(D+f))
ach=[]
feitas=[]
def chk(nome, cond, det=''):
    print(('ok   ' if cond else 'ERRO ')+nome+(' | '+det if (det and not cond) else ''))
    feitas.append(nome)
    if not cond:
        ach.append(nome)
        print(f'::warning title=Conferência dos dados::{nome}: {det[:300]}')   # aviso no resumo da execução do GitHub
def por_uf(L, iuf, ival=None, f=None):
    c=collections.defaultdict(float)
    for r in L:
        if f and not f(r): continue
        c[r[iuf]] += (r[ival] or 0) if ival is not None else 1
    return c
dif=lambda a,b: {k:(a.get(k),b.get(k)) for k in set(a)|set(b) if abs((a.get(k) or 0)-(b.get(k) or 0))>0.5}
# população
pop=J('populacao.json')['valores']; lm=J('luzes/municipios.json')
s=por_uf(lm['municipios'],4,2)
chk('população: municípios somam o estado (27)', not dif(pop,s), str(dif(pop,s))[:200])
chk('população: total', sum(pop.values())==lm['total']==203080756, f"{sum(pop.values())} {lm['total']}")
# lavouras
ag=J('agricultura.json')['valores']; le=J('lavouras/estados.json')['valores']; lmu=J('lavouras/municipios.json')
chk('agricultura.json = lavouras/estados (valor)', not dif(ag,{k:v['valor'] for k,v in le.items()}))
s=por_uf(lmu['municipios'],7,2); r={k:round(s[k]/ag[k],4) for k in ag if ag[k]}
chk('lavouras: municípios somam o estado (±1%)', all(0.99<=x<=1.01 for x in r.values()), str({k:x for k,x in r.items() if not 0.99<=x<=1.01}))
for uf,v in le.items():
    p=v['principais']
    if p and sum(x[1] for x in p)>v['valor']: chk(f'lavouras {uf}: 5 principais ≤ total', False)
    if p!=sorted(p,key=lambda x:-x[1]): chk(f'lavouras {uf}: principais em ordem', False)
print('     lavouras: principais conferidas')
# pecuária
pe=J('pecuaria/estados.json'); pm=J('pecuaria/municipios.json')
s=por_uf(pm['municipios'],4,2); e={k:v['bovino'] for k,v in pe['valores'].items()}
chk('pecuária: municípios somam o estado', not dif(e,s), str(dif(e,s))[:300])
chk('pecuária: total', pe['total_bovino']==sum(e.values())==pm['meta']['total'], f"{pe['total_bovino']} {sum(e.values())} {pm['meta']['total']}")
# energia
ee=J('energia/estados.json'); us=J('energia/usinas.json')
tip=['eol','sol','uhe','pch','cgh','bio','fos','nuc']
bad={k:(v['valor'],round(sum(v[t] for t in tip),1)) for k,v in ee['valores'].items() if abs(v['valor']-sum(v[t] for t in tip))>0.6}
chk('energia: fontes somam a potência do estado', not bad, str(bad))
chk('energia: total = soma dos estados', abs(ee['total_mw']-sum(v['valor'] for v in ee['valores'].values()))<2, f"{ee['total_mw']} {sum(v['valor'] for v in ee['valores'].values())}")
s=por_uf(us['usinas'],5,2); bad={k:(round(s[k]/1000),v['valor']) for k,v in ee['valores'].items() if s[k]/1000>v['valor']+1}
chk('energia: usinas ≥1 MW ≤ total do estado', not bad, str(bad))
chk('energia: meta total das usinas', abs(sum(u[2] for u in us['usinas'])/1000-us['meta']['total_mw'])<2 and abs(us['meta']['total_mw_todas']-ee['total_mw'])<2, f"{sum(u[2] for u in us['usinas'])/1000} {us['meta']} {ee['total_mw']}"[:200])
chk('energia: nenhuma usina < 1 MW na camada', min(u[2] for u in us['usinas'])>=1000)
# petróleo
pp=J('petroleo/producao_estados.json'); po=J('petroleo/pocos.json')
bad={k:(v['valor'], round(v['petroleo_bbl_dia']+v['gas_mil_m3_dia']*6.2898)) for k,v in pp['valores'].items() if abs(v['valor']-(v['petroleo_bbl_dia']+v['gas_mil_m3_dia']*6.2898))>max(3,0.001*v['valor'])}
chk('petróleo: boe = petróleo + gás × 6,2898', not bad, str(bad))
s=por_uf(po['pocos'],7,2); bad={k:(v['valor'],round(s.get(k,0))) for k,v in pp['valores'].items() if abs(v['valor']-s.get(k,0))>max(5,0.002*v['valor'])}
chk('petróleo: poços somam o estado', not bad, str(bad))
c=por_uf(po['pocos'],7); bad={k:(v['pocos'],c.get(k)) for k,v in pp['valores'].items() if v['pocos']!=c.get(k,0)}
chk('petróleo: contagem de poços por estado', not bad, str(bad))
chk('petróleo: total', abs(pp['total_boe_dia']-po['meta']['total_boe_d'])<=2 and abs(sum(v['valor'] for v in pp['valores'].values())+po['meta']['producao_sem_estado_boe_d']-pp['total_boe_dia'])<30, f"{pp['total_boe_dia']} {po['meta']['total_boe_d']} {sum(v['valor'] for v in pp['valores'].values())}")
print('     petróleo: poços com produção zero na camada "em produção":', sum(1 for p in po['pocos'] if not p[2]))
# celular
ce=J('celular/estados.json'); g5=J('celular/5g.json'); cm=J('celular/municipios.json')
c=por_uf(g5['municipios'],3); n=por_uf(cm['municipios'],4)
bad={k:(v['g5'],c.get(k,0),n.get(k)) for k,v in ce['valores'].items() if v['g5'][0]!=c.get(k,0) or v['g5'][1]!=n.get(k)}
chk('celular: municípios com 5G por estado', not bad, str(bad)[:300])
bad={k:v['g5_pct'] for k,v in ce['valores'].items() if abs(v['g5_pct']-100*v['g5'][0]/v['g5'][1])>0.06}
chk('celular: % de municípios com 5G', not bad, str(bad))
cu=J('celular/cobertura_5g_uf.json'); cb=J('celular/cobertura_5g.json')
# "com algum sinal" = % de moradores acima de zero antes de arredondar: fica entre os que têm % arredondada > 0 e os que têm qualquer indício
c=por_uf(cb['municipios'],8,None,lambda r:r[2]>0); c2=por_uf(cb['municipios'],8,None,lambda r:r[2]>0 or r[3]>0 or r[4]>0 or r[5]); n=por_uf(cb['municipios'],8)
bad={k:(v['municipios_com_5g'],c.get(k,0),c2.get(k,0),v['municipios'],n.get(k)) for k,v in cu['valores'].items() if not c.get(k,0)<=v['municipios_com_5g']<=c2.get(k,0) or v['municipios']!=n.get(k)}
chk('moradores com 5G: contagem de municípios', not bad, str(bad)[:300])
popm={(r[3],r[4]):r[2] for r in lm['municipios']}
num=collections.defaultdict(float); den=collections.defaultdict(float); sem=0
for r in cb['municipios']:
    p=popm.get((r[7],r[8]))
    if p is None: sem+=1; continue
    num[r[8]]+=p*r[2]; den[r[8]]+=p
bad={k:(v['valor'],round(num[k]/den[k],1)) for k,v in cu['valores'].items() if abs(v['valor']-num[k]/den[k])>0.15}
chk(f'moradores com 5G: média ponderada pela população (sem par: {sem})', not bad, str(bad))
bu=J('celular/banda_larga_uf.json'); bl=J('celular/banda_larga.json')
s=por_uf(bl['municipios'],10,3); bad={k:(v['acessos'],s.get(k)) for k,v in bu['valores'].items() if v['acessos']!=s.get(k)}
chk('banda larga: acessos dos municípios somam o estado', not bad, str(bad)[:300])
print('     banda larga Brasil:', json.dumps(bu['brasil'],ensure_ascii=False)[:200], 'soma UFs', sum(v['acessos'] for v in bu['valores'].values()))
bad={k:(v['valor'],round(100*v['acessos']/pop[k],1)) for k,v in bu['valores'].items() if abs(v['valor']-100*v['acessos']/pop[k])>2.5}
print('     banda larga: densidade × (acessos ÷ Censo 2022), diferença > 2,5 pontos:', bad or 'nenhuma')
vu=J('celular/velocidade_uf.json'); ve=J('celular/velocidade.json')
s=por_uf(ve['municipios'],10,3); bad={k:(v['testes'],s.get(k)) for k,v in vu['valores'].items() if v['testes']!=s.get(k)}
chk('velocidade: testes dos municípios somam o estado', not bad, str(bad)[:300])
chk('velocidade: total de testes', abs(sum(v['testes'] for v in vu['valores'].values())-ve['meta']['testes'])<=ve['meta']['testes']*0.001, f"{sum(v['testes'] for v in vu['valores'].values())} {ve['meta']['testes']}")
# defesa
de=J('defesa/estados.json'); dm=J('defesa/empresas.json')
chk('defesa: total', de['total']==de['ed']+de['eed']==sum(v['valor'] for v in de['valores'].values()), f"{de['total']} {de['ed']} {de['eed']} {sum(v['valor'] for v in de['valores'].values())}")
c=collections.Counter(); 
for r in dm['municipios']: c[r[3]]+=len(r[5])
bad={k:(v['valor'],c.get(k,0),v['sem_municipio']) for k,v in de['valores'].items() if v['valor']-v['sem_municipio']!=c.get(k,0) or v['eed']+v['ed']!=v['valor']}
chk('defesa: empresas por município somam o estado', not bad, str(bad))
# aeroportos e pedágios
ae=J('aeroportos/aeroportos.json'); A=ae['aeroportos']
chk('aeroportos: meta', len(A)==ae['meta']['aerodromos'] and sum(1 for a in A if (a[6] or 0)>=1000)==ae['meta']['com_passageiros'], f"{len(A)} {sum(1 for a in A if a[6])}")
print('     aeroportos: passageiros da camada', sum(a[6] or 0 for a in A), 'meta', ae['meta']['passageiros'], '| fora da lista:', json.dumps(ae['meta']['fora_da_lista'],ensure_ascii=False)[:160])
pd=J('trafego/pedagios.json'); P=pd['pracas']
chk('pedágios: meta', len(P)==pd['meta']['pracas'] and sum(1 for p in P if p[12]==0)==pd['meta']['com_numero'], f"{len(P)} {collections.Counter(p[12] for p in P)}")
bad=[(p[2],p[8],p[9]) for p in P if p[12]==0 and (not p[8] or p[9] is None or not 0<=p[9]<=100)]
chk('pedágios: valores válidos', not bad, str(bad)[:200])
# eletropostos
el=J('eletropostos.json')
print('     eletropostos brasil:', json.dumps(el['brasil'],ensure_ascii=False)[:200], '| regiões somam', sum((v['valor'] if isinstance(v,dict) else v) for v in el['regioes'].values()))
# coordenadas dentro do Brasil
for f,k,iu in [('luzes/municipios.json','municipios',4),('energia/usinas.json','usinas',5),('aeroportos/aeroportos.json','aeroportos',5),('trafego/pedagios.json','pracas',7),('defesa/empresas.json','municipios',3),('petroleo/pocos.json','pocos',7)]:
    L=J(f)[k]; fora=[r[:2]+[r[iu]] for r in L if not(-74.5<=r[0]<=-28 and -34.5<=r[1]<=5.6)]
    chk(f'{f}: pontos dentro da caixa do Brasil', not fora, str(fora[:5]))
print('ACHADOS:', ach or 'nenhum')
if '--registro' in sys.argv:   # no robô mensal: grava o resultado, para conferir depois sem abrir o GitHub
    from datetime import datetime, timezone
    Path(D + 'conferencia.json').write_text(json.dumps({"rodou_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "contas": len(feitas), "certas": len(feitas) - len(ach), "diferencas": ach}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
sys.exit(1 if ach else 0)
