import io,json,zipfile,hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import MultipleLocator
from matplotlib.colors import is_color_like
from scipy.stats import t as student_t
import streamlit as st
from analysis import baseline,fit,regression,MODELS
from mass_balance import inventory,oxidant_consumed_mol

st.set_page_config(page_title='Kinetic Lab',layout='wide')
st.title('Soil Kinetic Lab v1.0')
st.caption('토양·수용액·전체 오염물질 질량수지 · 상별 플로팅 · 토양/전체 반응속도 · 산화제 이용 · Figure Builder')
PALETTES={'Muted':['#6487A2','#C58C65','#789780','#A184A2','#8A8A8A','#B6A46B','#709DA1','#B57882'],'Colorblind':['#0072B2','#D55E00','#009E73','#CC79A7','#777777','#E69F00','#56B4E9','#A79B00'],'Deep muted':['#334E68','#356D69','#9A5348','#777548','#765A79','#586675','#986E3F','#805766']}
MARKERS={'○ 원':'o','□ 사각형':'s','△ 위 삼각형':'^','▽ 아래 삼각형':'v','◇ 마름모':'D','⬡ 육각형':'h','◁ 왼쪽 삼각형':'<','▷ 오른쪽 삼각형':'>'}

# All user-facing options use stable keys. Restore before any option widgets exist.
with st.sidebar:
    st.header('설정 파일')
    cfgup=st.file_uploader('설정 JSON 불러오기',type=['json'],key='_config_file')
    if st.button('설정 적용',disabled=cfgup is None):
        try:
            payload=json.loads(cfgup.getvalue());widgets=payload['widgets'];savedstyles=payload.get('styles',[])
            if payload.get('version') not in ['0.2','0.3','0.4','1.0'] or not isinstance(widgets,dict) or not isinstance(savedstyles,list):raise ValueError('v0.2~v0.4 또는 v1.0 설정 파일이 필요합니다.')
            allowed=('global_','p_','o_','plot_','effect_','util_','builder_','units_','soil_','total_')
            for key in list(st.session_state):
                if key.startswith(allowed) or key.startswith('style_editor_'):del st.session_state[key]
            for key,value in widgets.items():
                if key.startswith(allowed):st.session_state[key]=value
            st.session_state['_restored_styles']=savedstyles
            st.session_state['_restored_palette']=widgets.get('global_palette','Muted')
            st.success('설정을 적용했습니다. 데이터는 별도로 업로드하세요.')
        except Exception as e:st.error(str(e))
    st.header('공통 그래프 스타일')
    palette=st.selectbox('Palette',list(PALETTES),key='global_palette')
    available_fonts=sorted({f.name for f in font_manager.fontManager.ttflist if 'Display' not in f.name})
    preferred=[f for f in ['DejaVu Sans','DejaVu Serif','Arial','Times New Roman','Calibri','Malgun Gothic','Nimbus Sans','Nimbus Roman'] if f in available_fonts]
    font_choices=preferred+[f for f in available_fonts if f not in preferred]
    if st.session_state.get('global_font',font_choices[0]) not in font_choices:
        st.warning('저장된 폰트가 이 PC에 없어 DejaVu Sans로 변경합니다.')
        st.session_state['global_font']='DejaVu Sans'
    font=st.selectbox('Font (설치된 폰트)',font_choices,key='global_font')
    st.caption('실제 설치된 폰트만 표시합니다. Serif를 선택하면 변화가 쉽게 보입니다.')
    fs=st.number_input('축 제목 크기',6,30,12,key='global_fs');ticks=st.number_input('눈금 크기',6,30,10,key='global_ticks');leg=st.number_input('Legend 크기',6,25,9,key='global_leg')
    ms=st.slider('마커 크기',2.,12.,6.,key='global_ms');edge=st.slider('마커 테두리 두께',.3,3.,1.2,key='global_edge');lw=st.slider('선 두께',.5,3.,1.4,key='global_lw')
    boxed=st.checkbox('상단·오른쪽 테두리 표시',True,key='global_box')
    width=st.number_input('Panel 너비 (inch)',2.,10.,4.,key='global_width');height=st.number_input('Panel 높이 (inch)',2.,10.,3.3,key='global_height')
    fmt=st.selectbox('Export',['tiff','png','pdf','svg'],key='global_fmt');dpi=st.selectbox('DPI',[300,600,1200],index=1,key='global_dpi')
plt.rcParams.update({'font.family':font,'font.size':ticks,'axes.labelsize':fs,'legend.fontsize':leg,'axes.spines.top':boxed,'axes.spines.right':boxed,'svg.fonttype':'none','pdf.fonttype':42})
tabs=st.tabs(['① 데이터 입력·물질수지','② 오염물질 분석','③ 산화제 분석','④ 조건 비교','⑤ 산화제 이용','⑥ Figure Builder'])
def soil_demo():
    rng=np.random.default_rng(42);rows=[]
    for dose,k in [(0,.006),(5,.026),(10,.052),(20,.080)]:
        for rep in range(1,4):
            c0=110*rng.uniform(.96,1.04)
            for t in [0,5,10,20,30,45,60]:
                soil=max(.1,c0*np.exp(-k*t)+ (0 if t==0 else rng.normal(0,.6)))
                aqueous=max(0,.12*np.exp(-.02*t)+2.5*(np.exp(-.035*t)-np.exp(-.14*t)))
                aqueous=max(0,aqueous+(0 if t==0 else rng.normal(0,.025)))
                ox=10*np.exp(-(.002+.00018*dose)*t)
                rows.append([f'PS {dose} mM',rep,t,soil,aqueous,ox,dose])
    return pd.DataFrame(rows,columns=['condition','replicate','time','soil','aqueous','oxidant','dose'])

with tabs[0]:
    up=st.file_uploader('CSV / Excel 업로드',type=['csv','xlsx'])
    try:
        if up:
            if up.name.endswith('.xlsx'):
                book=pd.ExcelFile(up);sheet=st.selectbox('Sheet',book.sheet_names);raw=pd.read_excel(book,sheet_name=sheet)
            else:raw=pd.read_csv(up)
        else:
            raw=soil_demo();st.info('가상 토양–수용액 예제를 표시합니다. 실제 농도는 추출회수율·희석배수 등 보정 후 입력하세요.')
        st.download_button('예제 CSV',soil_demo().to_csv(index=False).encode(),'soil_example_long.csv')
        with st.expander('입력 형식 / 열 역할 지정',expanded=True):
            form=st.radio('형식',['Long','Wide'],horizontal=True)
            cols=list(raw.columns)
            def mapping(label,default,optional=False):
                choices=['(없음)']+cols if optional else cols
                return st.selectbox(label,choices,index=choices.index(default) if default in choices else 0)
            tc=mapping('Time','time')
            if form=='Long':
                cc=mapping('Condition','condition');rc=mapping('Replicate','replicate',True)
                sc=mapping('Soil (mg/kg dry soil)','soil');wc=mapping('Aqueous (mg/L)','aqueous');oc=mapping('Oxidant','oxidant',True)
                roles=[tc,cc,sc,wc]+([rc] if rc!='(없음)' else [])+([oc] if oc!='(없음)' else [])
                if len(set(roles))!=len(roles):raise ValueError('하나의 열에 여러 역할을 지정할 수 없습니다.')
                d=pd.DataFrame({'time':raw[tc],'condition':raw[cc],'replicate':raw[rc] if rc!='(없음)' else '1','soil':raw[sc],'aqueous':raw[wc]})
                if oc!='(없음)':d['oxidant']=raw[oc]
                extra=[c for c in cols if c not in roles and pd.api.types.is_numeric_dtype(raw[c])]
                xc=st.selectbox('숫자 조건 변수',['직접 입력']+extra,index=1+extra.index('dose') if 'dose' in extra else 0)
            else:
                st.caption('Wide: 각 행이 하나의 시간점이고 각 조건/반복별 토양·수용액 열을 한 쌍으로 지정합니다.')
                available=[c for c in cols if c!=tc]
                pairs=st.number_input('조건/반복 열 쌍 수',min_value=1,max_value=100,value=1,key='soil_wide_n')
                frames=[]
                for i in range(int(pairs)):
                    with st.expander(f'열 쌍 {i+1}',expanded=i==0):
                        c1,c2,c3,c4=st.columns(4)
                        cond=c1.text_input('Condition',value=f'Condition {i+1}',key=f'soil_wc_{i}')
                        rep=c2.text_input('Replicate',value='1',key=f'soil_wr_{i}')
                        sco=c3.selectbox('Soil 열',available,index=min(i*2,len(available)-1),key=f'soil_ws_{i}')
                        wco=c4.selectbox('Aqueous 열',available,index=min(i*2+1,len(available)-1),key=f'soil_ww_{i}')
                        oco=st.selectbox('Oxidant 열',['(없음)']+available,key=f'soil_wo_{i}')
                        if sco==wco or (oco!='(없음)' and oco in (sco,wco)):raise ValueError('열 쌍 내 측정 열이 중복되었습니다.')
                        f=pd.DataFrame({'time':raw[tc],'condition':cond,'replicate':rep,'soil':raw[sco],'aqueous':raw[wco]})
                        if oco!='(없음)':f['oxidant']=raw[oco]
                        frames.append(f)
                d=pd.concat(frames,ignore_index=True);xc='직접 입력'
        st.subheader('반응기 조건 (질량수지 계산)')
        a,b=st.columns(2)
        soil_g=a.number_input('토양 건조질량 (g)',min_value=.000001,value=10.,key='soil_default_g')
        water_ml=b.number_input('수용액 부피 (mL)',min_value=.000001,value=100.,key='soil_default_ml')
        st.caption('농도 입력 단위: 토양 mg/kg (건조), 수용액 mg/L. 조건별 질량·부피를 다르게 설정할 수 있습니다.')
        condnames=list(pd.Series(d.condition).dropna().astype(str).unique())
        geom=pd.DataFrame({'condition':condnames,'soil_g':soil_g,'water_ml':water_ml})
        geom=st.data_editor(geom,hide_index=True,disabled=['condition'],key='soil_geometry')
        d=inventory(d,geometry=geom)
        if 'oxidant' in d:
            d['oxidant']=pd.to_numeric(d.oxidant,errors='coerce')
            if ((d.oxidant.dropna()<0).any() or np.isinf(d.oxidant).any()):raise ValueError('산화제 농도를 확인하세요.')
        st.caption('total_mass = soil(mg/kg) × soil_g/1000 + aqueous(mg/L) × water_ml/1000. 잔존율은 각 반복의 전체 초기질량 기준입니다.')
        st.download_button('계산된 질량수지 CSV',d.to_csv(index=False).encode(),'soil_mass_balance.csv')
    except Exception as e:st.error(str(e));st.stop()
    conditions=list(d.condition.unique())
    meta=pd.DataFrame({'condition':conditions,'x':np.arange(len(conditions),dtype=float),'label':conditions,'color':[PALETTES[palette][i%8] for i in range(len(conditions))],'marker':[list(MARKERS)[i%8] for i in range(len(conditions))],'fill':['Open']*len(conditions)})
    if form=='Long' and xc!='직접 입력':
        for i,c in enumerate(conditions):
            vals=pd.to_numeric(raw.loc[raw[cc].astype(str)==c,xc],errors='coerce').dropna().unique()
            if len(vals)==1:meta.loc[i,'x']=vals[0]
            else:st.warning(f'{c}: 조건 변수 값이 하나가 아닙니다. x를 직접 확인하세요.')
    restored={r['condition']:r for r in st.session_state.get('_restored_styles',[]) if isinstance(r,dict) and 'condition' in r}
    if st.session_state.get('_restored_palette',palette)!=palette:restored={}
    for i,c in enumerate(conditions):
        if c in restored:
            for col in ['x','label','color','marker','fill']:
                if col in restored[c]:meta.loc[i,col]=restored[c][col]
    signature=hashlib.sha256((''.join(conditions)+palette).encode()).hexdigest()[:12]
    st.subheader('조건 스타일 · 모든 패널에서 공유')
    meta=st.data_editor(meta,hide_index=True,disabled=['condition'],key='style_editor_'+signature,column_config={'marker':st.column_config.SelectboxColumn('마커',options=list(MARKERS),required=True),'fill':st.column_config.SelectboxColumn('채움',options=['Open','Hollow','Filled'],required=True)})
    if not all(is_color_like(c) for c in meta.color) or not meta.marker.isin(MARKERS).all() or not meta.fill.isin(['Open','Hollow','Filled']).all():st.error('색(HEX), 마커, 채움을 확인하세요.');st.stop()
    if not np.isfinite(pd.to_numeric(meta.x,errors='coerce')).all():st.error('조건 x값은 유한한 숫자여야 합니다.');st.stop()
    styles=meta.set_index('condition').to_dict('index')
    st.caption('Open=흰색 채움, Hollow=투명, Filled=색 채움. 같은 마커·색을 지정하고 채움만 바꾸면 관련 실험을 묶을 수 있습니다. 독립 batch 반복과 기기 반복주입을 구분하세요.')
    with st.expander('단위'):
        timeunit=st.text_input('시간 단위','min',key='units_time');punit=st.text_input('토양 농도 단위','mg/kg',key='units_p');ounit=st.text_input('산화제 농도 단위','mM',key='units_o')
    st.dataframe(d.head(20),hide_index=True)

analyses={};options={};plots={};regtables=[]
def marker_style(cond):
    s=styles[cond]
    return dict(color=s['color'],marker=MARKERS[s['marker']],label=s['label'],markersize=ms,markeredgewidth=edge,markeredgecolor=s['color'],markerfacecolor=('none' if s['fill']=='Hollow' else 'white' if s['fill']=='Open' else s['color']))

def graph_settings(name,default_legend=True):
    prefix='plot_'+name+'_'
    with st.expander('그래프 설정 · '+name):
        cs=st.columns(3)
        legend=cs[0].checkbox('Legend 표시',default_legend,key=prefix+'legend');loc=cs[1].selectbox('Legend 위치',['best','upper right','upper left','lower right','lower left','center right','center left','upper center','lower center'],key=prefix+'loc');points=cs[2].checkbox('실험점 표시',True,key=prefix+'points')
        cs=st.columns(2);lines=cs[0].checkbox('피팅선 표시',True,key=prefix+'lines');equation=cs[1].checkbox('회귀식 표시',False,key=prefix+'equation')
        cs=st.columns(2);xlabel=cs[0].text_input('X축 제목 (빈칸=자동)',key=prefix+'xlabel');ylabel=cs[1].text_input('Y축 제목 (빈칸=자동)',key=prefix+'ylabel')
        st.caption('첨자: $S_2O_8^{2-}$ · $C/C_0$ · $k$ ($min^{-1}$). 달러 기호를 포함해 입력하세요.')
        if xlabel or ylabel:
            preview,ax=plt.subplots(figsize=(4,1));ax.axis('off');ax.text(.01,.65,xlabel or 'X axis');ax.text(.01,.15,ylabel or 'Y axis')
            try:st.pyplot(preview)
            except Exception as e:st.warning('첨자 문법 확인: '+str(e))
            finally:plt.close(preview)
        cs=st.columns(2);xlim=cs[0].text_input('X축 범위 min,max',key=prefix+'xlim');ylim=cs[1].text_input('Y축 범위 min,max',key=prefix+'ylim')
        cs=st.columns(2);xtick=cs[0].text_input('X축 눈금 간격',help='예: 10 → 10 단위 간격. 빈칸은 자동.',key=prefix+'xtick');ytick=cs[1].text_input('Y축 눈금 간격',help='양수 숫자. 빈칸은 자동.',key=prefix+'ytick')
    options[name]=dict(legend=legend,loc=loc,points=points,lines=lines,equation=equation,xlabel=xlabel,ylabel=ylabel,xlim=xlim,ylim=ylim,xtick=xtick,ytick=ytick)

def finish(ax,name,xlabel,ylabel):
    op=options[name];ax.set_xlabel(op['xlabel'] or xlabel,fontfamily=font);ax.set_ylabel(op['ylabel'] or ylabel,fontfamily=font)
    for axis in ['x','y']:
        if op[axis+'lim']:
            bounds=list(map(float,op[axis+'lim'].split(',')))
            if len(bounds)!=2 or bounds[0]>=bounds[1]:raise ValueError('축 범위는 min,max (min<max)로 입력하세요.')
            getattr(ax,'set_'+axis+'lim')(bounds)
        if op[axis+'tick']:
            step=float(op[axis+'tick'])
            if not np.isfinite(step) or step<=0:raise ValueError('눈금 간격은 유한한 양수여야 합니다.')
            getattr(ax,axis+'axis').set_major_locator(MultipleLocator(step))
    ax.tick_params(top=False,right=False,labelsize=ticks)
    for text in ax.get_xticklabels()+ax.get_yticklabels()+ax.texts:
        text.set_fontfamily(font)
    if op['legend'] and ax.get_legend_handles_labels()[0]:ax.legend(frameon=False,loc=op['loc'],prop={'family':font,'size':leg})

def show_figure(fig):
    # Explicit image bytes ensure the display uses the same updated Figure as export.
    preview_bytes=io.BytesIO();fig.savefig(preview_bytes,format='png',dpi=150,bbox_inches='tight',facecolor='white')
    st.image(preview_bytes.getvalue())

def render(name):
    fig,ax=plt.subplots(figsize=(width,height))
    try:
        plots[name](ax);fig.tight_layout();show_figure(fig)
        buf=io.BytesIO();fig.savefig(buf,format=fmt,dpi=dpi,bbox_inches='tight',facecolor='white');st.download_button('그래프 저장 · '+name,buf.getvalue(),name.replace(' ','_')+'.'+fmt,key='download_'+name)
    except Exception as e:st.error(name+': '+str(e))
    finally:plt.close(fig)

def calculate(col,cfg):
    source=baseline(d,col) if cfg['norm'] else d.assign(normalized=d[col]);result=[];curves={};residual=[];failures=[]
    if cfg['model']=='None':return dict(source=source,summary=pd.DataFrame(),curves=curves,residual=pd.DataFrame(),cfg=cfg,failures=[])
    for cond,g in source.groupby('condition',sort=False):
        subset=g[g.time.between(cfg['tmin'],cfg['tmax'])]
        groups=[('mean',subset.groupby('time',as_index=False).normalized.mean())] if cfg['strategy']=='mean' else list(subset.groupby('replicate'))
        fitted=[]
        for rep,h in groups:
            try:
                h=h.sort_values('time');r,pred=fit(h.time,h.normalized,cfg['model'],cfg['fixed']);r.update(condition=cond,replicate=rep);fitted.append(r)
                residual.extend([dict(condition=cond,replicate=rep,time=tm,observed=y,predicted=yp,residual=y-yp) for tm,y,yp in zip(h.time,h.normalized,pred)])
            except Exception as e:failures.append(f'{cond}/{rep}: {e}')
        if not fitted:continue
        f=pd.DataFrame(fitted);curves[cond]=fitted
        if cfg['strategy']=='mean':r=fitted[0].copy();r.update(SD=np.nan,n_replicates=g.replicate.nunique())
        else:
            n=len(f);sd=f.k.std(ddof=1);se=sd/np.sqrt(n);margin=student_t.ppf(.975,n-1)*se if n>1 else np.nan
            r=dict(condition=cond,k=f.k.mean(),SE=se,SD=sd,CI_low=f.k.mean()-margin,CI_high=f.k.mean()+margin,R2=np.nan,n=f.n.sum(),n_replicates=n)
        result.append(r)
    return dict(source=source,summary=pd.DataFrame(result),curves=curves,residual=pd.DataFrame(residual),cfg=cfg,failures=failures)

def kinetics(ax,col,name):
    a=analyses[col];cfg=a['cfg'];op=options[name]
    for cond,g in a['source'].groupby('condition',sort=False):
        agg=g.groupby('time').normalized.agg(['mean','std']);s=marker_style(cond)
        if op['points']:
            ax.errorbar(agg.index,agg['mean'],yerr=agg['std'].fillna(0),linestyle='none',capsize=3,**s)
            if cfg['raw']:
                ax.plot(g.time,g.normalized,linestyle='none',alpha=.3,**{**s,'label':'_nolegend_','markersize':ms*.7})
        if op['lines'] and cond in a['curves']:
            xx=np.linspace(cfg['tmin'],cfg['tmax'],200)
            for r in a['curves'][cond]:ax.plot(xx,MODELS[cfg['model']](xx,r['A'],r['k']),color=s['color'],lw=lw,label=s['label'] if not op['points'] else '_nolegend_')
    if op['equation'] and cfg['model']!='None':ax.text(.03,.97,{'PFO':r'$C=Ae^{-kt}$','Second-order':r'$C=A/(1+Akt)$','Zero-order':r'$C=A-kt$'}[cfg['model']],transform=ax.transAxes,va='top')
    finish(ax,name,f'Time ({timeunit})',r'$M/M_0$' if cfg['norm'] else (f'{col.capitalize()} (mg)' if col in ['soil_mass','total_mass'] else f'{col.capitalize()} ({ounit})'))

def residualplot(ax,col,name):
    if options[name]['points']:
        for cond,g in analyses[col]['residual'].groupby('condition',sort=False):ax.plot(g.time,g.residual,linestyle='none',**marker_style(cond))
    ax.axhline(0,color='#777777',lw=lw);finish(ax,name,f'Time ({timeunit})','Residual')

with tabs[1]:
    st.caption('토양·전체: PFO 등 속도 피팅 · 수용액: 피팅 없이 데이터만 표시')
    for phase,col,pref in [('토양','soil_mass','p_'),('전체','total_mass','total_')]:
        with st.expander(phase+' 피팅 설정',expanded=phase=='토양'):
            cs=st.columns(3)
            model=cs[0].selectbox('Kinetic model',['None']+list(MODELS),index=1,key=pref+'model')
            norm=cs[1].checkbox('M/M₀ 사용',True,key=pref+'norm')
            fixed=cs[2].checkbox('A=1 고정 (정규화 시)',False,key=pref+'fixed') and norm
            cs=st.columns(3)
            strategy=cs[0].selectbox('k 추정 방식',['평균 시간곡선 피팅','각 반복실험 별도 피팅'],key=pref+'strategy')
            tmin=cs[1].number_input('Fit 시작 시간',value=float(d.time.min()),key=pref+'tmin')
            tmax=cs[2].number_input('Fit 종료 시간',value=float(d.time.max()),key=pref+'tmax')
            rawpoints=st.checkbox('개별 반복 데이터 표시',False,key=pref+'raw')
        cfg=dict(model=model,norm=norm,fixed=fixed,strategy='mean' if strategy.startswith('평균') else 'replicate',tmin=tmin,tmax=tmax,raw=rawpoints)
        try:
            if tmin>=tmax:raise ValueError('Fit 시간 범위가 올바르지 않습니다.')
            result=calculate(col,cfg);analyses[col]=result
            for msg in result['failures']:st.warning(msg)
            if not result['summary'].empty:
                with st.expander(phase+' k 결과'):
                    st.dataframe(result['summary'],hide_index=True)
                    st.download_button('k 결과 CSV',result['summary'].to_csv(index=False).encode(),f'kinetic_{col}.csv',key='soil_k_'+col)
            elif model!='None':st.warning(phase+': 피팅 가능한 데이터가 없습니다.')
        except Exception as e:st.error(phase+': '+str(e))
    aqcfg=dict(model='None',norm=False,fixed=False,strategy='mean',tmin=float(d.time.min()),tmax=float(d.time.max()),raw=False)
    analyses['aqueous_mass']=calculate('aqueous_mass',aqcfg)
    st.info('수용액은 피팅하지 않습니다. 검출한계 및 초기 농도 0도 원자료 그대로 시각화합니다.')
    for col,name in [('soil_mass','Soil kinetics'),('aqueous_mass','Aqueous kinetics'),('total_mass','Total kinetics')]:
        graph_settings(name)
        plots[name]=lambda ax,col=col,name=name:kinetics(ax,col,name)
    choice=st.radio('그래프 보기',['3상 패널','토양','수용액','전체'],horizontal=True,key='soil_phase')
    if choice=='3상 패널':
        fig,axes=plt.subplots(1,3,figsize=(width*3,height))
        try:
            for ax,name in zip(axes,['Soil kinetics','Aqueous kinetics','Total kinetics']):plots[name](ax)
            fig.tight_layout();show_figure(fig)
            buf=io.BytesIO();fig.savefig(buf,format=fmt,dpi=dpi,bbox_inches='tight',facecolor='white')
            st.download_button('3상 패널 저장',buf.getvalue(),'three_phase_kinetics.'+fmt)
        except Exception as e:st.error(str(e))
        finally:plt.close(fig)
    else:render({'토양':'Soil kinetics','수용액':'Aqueous kinetics','전체':'Total kinetics'}[choice])
    for col,name in [('soil_mass','Soil residuals'),('total_mass','Total residuals')]:
        if col in analyses and not analyses[col]['residual'].empty:
            graph_settings(name,False)
            plots[name]=lambda ax,col=col,name=name:residualplot(ax,col,name)
            with st.expander(name):render(name)

with tabs[2]:
    if 'oxidant' not in d:st.info('산화제 열이 없어 산화제 분석이 비활성화됩니다.')
    else:
        col='oxidant';pref='o_'
        with st.expander('산화제 분석 설정',expanded=True):
            cs=st.columns(3)
            model=cs[0].selectbox('Kinetic model',['None']+list(MODELS),index=0,key=pref+'model')
            norm=cs[1].checkbox('C/C₀ 사용',True,key=pref+'norm')
            fixed=cs[2].checkbox('A=1 고정 (정규화 시)',False,key=pref+'fixed') and norm
            cs=st.columns(3)
            strategy=cs[0].selectbox('k 추정 방식',['평균 시간곡선 피팅','각 반복실험 별도 피팅'],key=pref+'strategy')
            tmin=cs[1].number_input('Fit 시작 시간',value=float(d.time.min()),key=pref+'tmin')
            tmax=cs[2].number_input('Fit 종료 시간',value=float(d.time.max()),key=pref+'tmax')
            rawpoints=st.checkbox('개별 반복 데이터 표시',False,key=pref+'raw')
        cfg=dict(model=model,norm=norm,fixed=fixed,strategy='mean' if strategy.startswith('평균') else 'replicate',tmin=tmin,tmax=tmax,raw=rawpoints)
        try:
            a=calculate(col,cfg);analyses[col]=a
            for message in a['failures']:st.warning(message)
            if not a['summary'].empty:
                st.dataframe(a['summary'],hide_index=True)
                st.download_button('k 결과 CSV',a['summary'].to_csv(index=False).encode(),'oxidant_k.csv')
            name='Oxidant kinetics';graph_settings(name);plots[name]=lambda ax:kinetics(ax,'oxidant',name);render(name)
            if not a['residual'].empty:
                name='Oxidant residuals';graph_settings(name,False);plots[name]=lambda ax:residualplot(ax,'oxidant',name)
                with st.expander('잔차 확인'):render(name)
        except Exception as e:st.warning(str(e))

def coefficient_table(table):
    return table.assign(term=table.term.map({'x^0':'Intercept','x^1':'Slope','x^2':'Quadratic coefficient'}))

def equation_text(table,r2):
    values=dict(zip(table.term,table.estimate));a=values.get('x^0',0);b=values.get('x^1',0);c=values.get('x^2')
    return f'y = {a:.4g} {b:+.4g} x'+(f' {c:+.4g} x²' if c is not None else '')+f'\nR² = {r2:.3f}'

def k_unit(col):
    cfg=analyses[col]['cfg'];cu='C/C₀' if cfg['norm'] else ('mg' if col in ['soil_mass','total_mass'] else ounit)
    if cfg['model']=='PFO':return f'{timeunit}⁻¹'
    if cfg['model']=='Second-order':return f'({cu})⁻¹ {timeunit}⁻¹'
    return f'{cu} {timeunit}⁻¹'

def kplot(ax,col,name,opts,effect,reg):
    summary=analyses[col]['summary'];op=options[name]
    if op['points']:
        for i,r in enumerate(summary.itertuples()):
            s=marker_style(r.condition);xx=float(styles[r.condition]['x']) if effect else i;err=None
            if opts['error']=='95% CI' and np.isfinite(r.CI_low):err=np.array([[r.k-r.CI_low],[r.CI_high-r.k]])
            elif opts['error']=='SE' and np.isfinite(r.SE):err=r.SE
            elif opts['error']=='반복 k의 SD' and np.isfinite(r.SD):err=r.SD
            if not effect and opts['bar']:
                ax.bar(xx,r.k,color=s['color'],width=.65);ax.errorbar(xx,r.k,yerr=err,fmt='none',color='#333333',capsize=3)
            else:ax.errorbar(xx,r.k,yerr=err,linestyle='none',capsize=3,**s)
    if effect and reg is not None:
        table,fn,r2=reg;xx=np.array([float(styles[c]['x']) for c in summary.condition]);grid=np.linspace(xx.min(),xx.max(),200)
        if op['lines']:ax.plot(grid,fn(grid),color='#444444',lw=lw)
        if op['equation']:ax.text(.03,.97,equation_text(table,r2),transform=ax.transAxes,va='top',fontsize=ticks)
    if not effect:ax.set_xticks(range(len(summary)),[styles[c]['label'] for c in summary.condition],rotation=25,ha='right')
    finish(ax,name,opts['xname'] if effect else 'Condition',f'k_{col} ({k_unit(col)})')

with tabs[3]:
    st.caption('조건 회귀는 조건별 k에 대한 비가중 회귀입니다. 서로 다른 모델/단위의 k는 직접 비교하지 마세요.')
    st.subheader('수용액 특성 비교 (피팅 없음)')
    aqpeak=d.loc[d.groupby(['condition','replicate'])['aqueous'].idxmax(),['condition','replicate','time','aqueous']].rename(columns={'time':'peak_time','aqueous':'peak_concentration_mg_L'})
    aqsummary=aqpeak.groupby('condition',as_index=False).agg(peak_concentration_mean=('peak_concentration_mg_L','mean'),peak_concentration_sd=('peak_concentration_mg_L','std'),peak_time_mean=('peak_time','mean'),peak_time_sd=('peak_time','std'))
    st.dataframe(aqsummary,hide_index=True)
    st.caption('측정된 시간점 가운데 최대 수용액 농도를 선택합니다. 모델로 추정한 최대값이 아니며, 동일 최대값이면 최초 관측시점을 사용합니다.')
    st.download_button('수용액 최대값 요약 CSV',aqsummary.to_csv(index=False).encode(),'aqueous_peak_summary.csv',key='aq_peak_csv')
    peakmetric=st.selectbox('수용액 비교 지표',['최대 농도 (mg/L)','최대 농도 도달시간 ('+timeunit+')'],key='effect_aq_peakmetric')
    peakchart=st.selectbox('수용액 비교 그래프',['Bar','Scatter'],key='effect_aq_peakchart')
    peakname='Aqueous peak comparison'
    graph_settings(peakname,False)
    def aqueous_peak_plot(ax):
        isconc=peakmetric.startswith('최대 농도 (')
        c='peak_concentration_mean' if isconc else 'peak_time_mean'
        sd='peak_concentration_sd' if isconc else 'peak_time_sd'
        for i,r in enumerate(aqsummary.to_dict('records')):
            cond=r['condition'];x=i if peakchart=='Bar' else float(styles[cond]['x']);s=marker_style(cond)
            y=float(r[c]);err=float(r[sd]) if pd.notna(r[sd]) else 0
            if peakchart=='Bar':
                ax.bar(x,y,color=s['color'],width=.65)
                ax.errorbar(x,y,yerr=err,fmt='none',color='#333333',capsize=3)
            else:
                ax.errorbar(x,y,yerr=err,linestyle='none',capsize=3,**s)
        if peakchart=='Bar':ax.set_xticks(range(len(aqsummary)),[styles[c]['label'] for c in aqsummary.condition],rotation=25,ha='right')
        finish(ax,peakname,'Condition' if peakchart=='Bar' else 'Condition variable', 'Aqueous peak (mg/L)' if isconc else f'Time to peak ({timeunit})')
    plots[peakname]=aqueous_peak_plot
    render(peakname)

    for col,a in analyses.items():
        if a['summary'].empty or col=='aqueous_mass':continue
        st.subheader({'soil_mass':'토양','total_mass':'전체','oxidant':'산화제'}.get(col,col))
        prefix='effect_'+col+'_';cs=st.columns(3)
        kind=cs[0].selectbox('조건–k 회귀',['None','Linear','Quadratic'],key=prefix+'kind');error=cs[1].selectbox('k Error bar',['95% CI','SE','반복 k의 SD','없음'],key=prefix+'error');chart=cs[2].selectbox('k 비교 그래프 형태',['Bar','Scatter'],key=prefix+'chart');bar=chart=='Bar'
        xname=st.text_input('조건 X축 제목','Oxidant dose (mM)' if col!='oxidant' else 'Condition variable',key=prefix+'xname');reg=None
        if error=='반복 k의 SD' and a['cfg']['strategy']=='mean':st.warning('반복 k의 SD는 각 반복실험 별도 피팅에서만 표시됩니다.')
        if bar:st.caption('Bar: 조건 이름으로 비교합니다. Scatter를 선택하면 숫자 조건 x값과 회귀선을 표시합니다.')
        if kind=='None':st.info('조건 회귀 꺼짐 · Linear 또는 Quadratic을 선택하면 선을 계산합니다.')
        else:
            try:
                reg=regression([float(styles[c]['x']) for c in a['summary'].condition],a['summary'].k,kind)
                st.success('조건 회귀 피팅 성공');st.code(equation_text(reg[0],reg[2]),language=None);st.dataframe(coefficient_table(reg[0]),hide_index=True)
                regtables.append(reg[0].assign(group=col+'_condition',R2=reg[2]))
            except Exception as e:st.warning('조건 회귀 피팅 실패: '+str(e))
        opts=dict(error=error,bar=bar,xname=xname)
        effect=not bar
        name=col.capitalize()+' k comparison';graph_settings(name,effect)
        plots[name]=lambda ax,col=col,name=name,opts=opts,effect=effect,reg=reg:kplot(ax,col,name,opts,effect,reg);render(name)

delta=None;utilregs={}
with tabs[4]:
    if 'oxidant' not in d:st.info('산화제 농도를 입력하면 이용효율 분석이 활성화됩니다.')
    else:
        with st.expander('이용효율 설정',expanded=True):
            kind=st.selectbox('제거량–산화제 소모량 회귀',['None','Linear'],index=1,key='util_kind')
            origin=st.checkbox('원점 통과',False,key='util_origin')
            pMW=st.number_input('오염물질 분자량 (g/mol)',min_value=.001,value=296.15,key='util_pmw')
            cs=st.columns(2)
            ou=cs[0].selectbox('산화제 농도 단위',['mM','mg/L','µg/L','µM','mol/L'],key='util_ou')
            oMW=cs[1].number_input('산화제 분자량 (g/mol)',min_value=.001,value=152.17,key='util_omw')
            stoich=st.number_input('모물질 1 mol당 이론적 산화제 요구량 (mol, 선택)',min_value=0.,value=0.,key='util_stoich')
            st.caption('Y: 전체 상에서 소실된 모물질 mol, X: 수용액에서 측정한 산화제 감소 mol. 제거량은 무기화량이 아닙니다. 이론적 산화제 요구량은 반응식/종말점을 검증한 경우에만 입력하세요.')
        try:
            delta=oxidant_consumed_mol(d,ou,oMW)
            delta['removed_mol']=delta.removed_mass/1000./pMW
            delta['molar_removal_ratio']=np.where(delta.oxidant_consumed_mol>0,delta.removed_mol/delta.oxidant_consumed_mol,np.nan)
            if stoich>0:delta['apparent_stoichiometric_efficiency']=stoich*delta.molar_removal_ratio
            if kind!='None':
                for cond,g in delta.groupby('condition',sort=False):
                    agg=g.groupby('time')[['oxidant_consumed_mol','removed_mol']].mean().dropna()
                    try:
                        reg=regression(agg.oxidant_consumed_mol,agg.removed_mol,origin=origin)
                        utilregs[cond]=reg
                        st.write(styles[cond]['label']);st.code(equation_text(reg[0],reg[2]),language=None)
                        st.dataframe(coefficient_table(reg[0]),hide_index=True)
                        regtables.append(reg[0].assign(group=cond+'_utilization',R2=reg[2]))
                    except Exception as e:st.warning(cond+' 회귀 실패: '+str(e))
            st.download_button('산화제 이용 자료 CSV',delta.to_csv(index=False).encode(),'oxidant_utilization.csv')
            name='Oxidant utilization';graph_settings(name)
            def utilization(ax):
                op=options['Oxidant utilization'];eq=[]
                for cond,g in delta.groupby('condition',sort=False):
                    agg=g.groupby('time')[['oxidant_consumed_mol','removed_mol']].mean().dropna()
                    if op['points']:ax.plot(agg.oxidant_consumed_mol,agg.removed_mol,linestyle='none',**marker_style(cond))
                    if cond in utilregs:
                        table,fn,r2=utilregs[cond]
                        xx=np.linspace(agg.oxidant_consumed_mol.min(),agg.oxidant_consumed_mol.max(),100)
                        if op['lines']:ax.plot(xx,fn(xx),color=styles[cond]['color'],lw=lw,label=styles[cond]['label'] if not op['points'] else '_nolegend_')
                        eq.append(styles[cond]['label']+': '+equation_text(table,r2))
                if op['equation']:ax.text(.03,.97,'\n'.join(eq),transform=ax.transAxes,va='top',fontsize=max(6,ticks-2))
                finish(ax,name,'Oxidant consumed (mol)','Total parent compound removed (mol)')
            plots[name]=utilization;render(name)
        except Exception as e:st.warning(str(e))
with tabs[5]:
    st.caption('패널별 legend·축·표시 옵션은 각 분석 탭의 그래프 설정을 따릅니다. 선택 순서가 panel 순서입니다.')
    defaults=[n for n in ['Soil kinetics','Aqueous kinetics','Total kinetics','Soil_mass k comparison','Total_mass k comparison','Oxidant kinetics','Oxidant utilization','Aqueous peak comparison'] if n in plots]
    # Prevent old selections of a disabled oxidant fit from invalidating the builder.
    if 'builder_selected' in st.session_state:
        renamed=[n.replace(' condition effect',' k comparison') for n in st.session_state['builder_selected']]
        st.session_state['builder_selected']=list(dict.fromkeys(n for n in renamed if n in plots))
    selected=st.multiselect('Panel 순서',list(plots),default=None if 'builder_selected' in st.session_state else defaults,key='builder_selected')
    cs=st.columns(3);ncol=cs[0].selectbox('열 수',[1,2,3],index=1,key='builder_ncol');spacing=cs[1].slider('Panel 간격',.2,1.,.45,key='builder_spacing');labels=cs[2].checkbox('(a), (b) Panel 이름',True,key='builder_labels')
    if selected:
        nrow=int(np.ceil(len(selected)/ncol));fig,axs=plt.subplots(nrow,ncol,figsize=(width*ncol,height*nrow),squeeze=False)
        try:
            for i,ax in enumerate(axs.flat):
                if i>=len(selected):ax.set_visible(False);continue
                plots[selected[i]](ax)
                if labels:ax.text(-.15,1.07,f'({chr(97+i)})',transform=ax.transAxes,fontweight='bold',fontsize=fs+2)
            fig.subplots_adjust(wspace=spacing,hspace=spacing);show_figure(fig);buf=io.BytesIO();fig.savefig(buf,format=fmt,dpi=dpi,bbox_inches='tight',facecolor='white');st.download_button('완성 Figure 저장',buf.getvalue(),'publication_figure.'+fmt)
        except Exception as e:st.error('Figure 설정 확인: '+str(e))
        finally:plt.close(fig)
    allowed=('global_','p_','o_','plot_','effect_','util_','builder_','units_','soil_','total_')
    settings={'version':'1.0','widgets':{k:v for k,v in st.session_state.items() if k.startswith(allowed)},'styles':meta.to_dict('records')}
    settings_json=json.dumps(settings,ensure_ascii=False,indent=2)
    st.download_button('설정 JSON 저장',settings_json.encode(),'settings_soil_v10.json')
    bundle=io.BytesIO()
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('input_canonical.csv',d.to_csv(index=False));z.writestr('settings_soil_v10.json',settings_json)
        for col,a in analyses.items():
            z.writestr(f'kinetic_{col}.csv',a['summary'].to_csv(index=False));z.writestr(f'residuals_{col}.csv',a['residual'].to_csv(index=False))
            if a['curves']:z.writestr(f'individual_fits_{col}.csv',pd.concat([pd.DataFrame(v) for v in a['curves'].values()]).to_csv(index=False))
        z.writestr('aqueous_peak_summary.csv',aqsummary.to_csv(index=False))
        if delta is not None:z.writestr('oxidant_utilization.csv',delta.to_csv(index=False))
        if regtables:z.writestr('regression_results.csv',coefficient_table(pd.concat(regtables,ignore_index=True)).to_csv(index=False))
    st.download_button('분석 기록 ZIP',bundle.getvalue(),'analysis_record.zip')
