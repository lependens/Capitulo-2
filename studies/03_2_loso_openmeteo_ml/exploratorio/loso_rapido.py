import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor as HGB
from pathlib import Path
R=str(Path(__file__).resolve().parents[3])+'/'
st=pd.read_csv(R+'config/stations.csv').set_index('station_code')
om=pd.read_csv(R+'data/processed/openmeteo_archive.csv')
ref=pd.concat([pd.read_csv(R+'data/reference/reference_2004_2019.csv'),pd.read_csv(R+'data/reference/reference_2020_2025.csv')])
ref=ref[ref.evaluated_PM.astype(str).str.lower()=='true'][['station_code','date','ET0_PM_FAO56_V1']].rename(columns={'ET0_PM_FAO56_V1':'pm'}).dropna()
si=pd.read_csv(R+'data/reference/siar_inputs_2020_2025.csv')[['station_code','date','TempMax','TempMin','HumedadMedia','Radiacion']]
d=ref.merge(om,on=['station_code','date']).merge(si,on=['station_code','date'],how='left')
d['date']=pd.to_datetime(d.date); d['year']=d.date.dt.year; d['month']=d.date.dt.month
doy=d.date.dt.dayofyear; d['s']=np.sin(2*np.pi*doy/365.25); d['c']=np.cos(2*np.pi*doy/365.25)
lat=np.radians(d.station_code.map(st.latitude_deg)); d['alt']=d.station_code.map(st.altitude_m); d['lat']=np.degrees(lat)
dr=1+0.033*np.cos(2*np.pi*doy/365); de=0.409*np.sin(2*np.pi*doy/365-1.39); ws=np.arccos(-np.tan(lat)*np.tan(de))
d['Ra']=24*60/np.pi*0.082*dr*(ws*np.sin(lat)*np.sin(de)+np.cos(lat)*np.cos(de)*np.sin(ws))
d=d.dropna(subset=['et0_om_mm','tmax_c','tmin_c','shortwave_sum_mj_m2','rh_mean_pct','wind10_mean_ms'])
OM=['et0_om_mm','tmax_c','tmin_c','shortwave_sum_mj_m2','wind10_mean_ms','rh_mean_pct','s','c','Ra','alt']
TEST=(d.year>=2023)
# coords for nearest
def dist(a,b):
    la1,lo1,la2,lo2=map(np.radians,[st.latitude_deg[a],st.longitude_deg_derived[a],st.latitude_deg[b],st.longitude_deg_derived[b]])
    return 6371*2*np.arcsin(np.sqrt(np.sin((la2-la1)/2)**2+np.cos(la1)*np.cos(la2)*np.sin((lo2-lo1)/2)**2))
codes=list(st.index); pmw=d.pivot_table(index='date',columns='station_code',values='pm')
rows=[]
def m(name,s,y,p):
    e=p-y; rows.append((name,s,len(e),np.sqrt(np.mean(e**2)),np.mean(e)))
for s in codes:
    te=d[TEST&(d.station_code==s)&d.TempMax.notna()&d.HumedadMedia.notna()]
    if len(te)==0: continue
    oth=d[d.station_code!=s]; y=te.pm.values
    m('OM crudo',s,y,te.et0_om_mm.values)
    dev=oth[oth.year<=2019]; a=dev.groupby('month').apply(lambda g:(g.et0_om_mm*g.pm).sum()/(g.et0_om_mm**2).sum())
    m('OM+AHC mensual (otras 8)',s,y,te.et0_om_mm.values*te.month.map(a).values)
    near=sorted([o for o in codes if o!=s],key=lambda o:dist(s,o))[0]
    pn=pmw[near].reindex(te.date).values; ok=~np.isnan(pn)
    m(f'PM estación más cercana ({near}, {dist(s,near):.0f} km)',s,y[ok],pn[ok])
    for name,F,trainmask in [('ML solo Open-Meteo',OM,oth.year<=2022),
                             ('ML sensor T + Open-Meteo',OM+['TempMax','TempMin'],(oth.year>=2020)&(oth.year<=2022)),
                             ('ML sensor T+HR + Open-Meteo',OM+['TempMax','TempMin','HumedadMedia'],(oth.year>=2020)&(oth.year<=2022)),
                             ('ML solo sensor T (+Ra, calendario)',['TempMax','TempMin','Ra','s','c','alt'],(oth.year>=2020)&(oth.year<=2022)),
                             ('ML sensor T+HR (+Ra) [tipo Valiantzas]',['TempMax','TempMin','HumedadMedia','Ra','s','c','alt'],(oth.year>=2020)&(oth.year<=2022))]:
        tr=oth[trainmask].dropna(subset=F)
        mod=HGB(max_iter=400,learning_rate=0.05,random_state=0).fit(tr[F],tr.pm)
        m(name,s,y,np.clip(mod.predict(te[F]),0,None))
r=pd.DataFrame(rows,columns=['modelo','est','n','rmse','sesgo'])
r['se']=r.rmse**2*r.n
g=r.groupby('modelo').apply(lambda x:pd.Series({'RMSE global':np.sqrt(x.se.sum()/x.n.sum()),'sesgo':np.average(x.sesgo,weights=x.n),'peor est.':x.rmse.max(),'n':x.n.sum()}))
print(g.sort_values('RMSE global').round(3).to_string())
print(r.pivot_table(index='est',columns='modelo',values='rmse').round(2).to_string())
