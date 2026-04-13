"""
05_analyze_tags.py
================================================================================
[목적]
    03c 요약 CSV를 읽어 전체 태그 빈도를 분석하고 최종 태그 목록을 확정한다.

[입력 파일]
    data/interim/03_steamspy_usertags_summary.csv

[출력 파일]
    data/interim/05_tag_analysis/05_tag_exclusion_table.csv
    data/interim/05_tag_analysis/05_selected_tags_final.csv
    data/interim/05_tag_analysis/05_tag_selection_report.png
================================================================================
"""

import pandas as pd, json, numpy as np, os
from collections import Counter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap

from project_paths import (
    SELECTED_TAGS_CSV,
    TAG_ANALYSIS_DIR,
    TAG_EXCLUSION_CSV,
    TAG_SELECTION_REPORT_PNG,
    USERTAGS_SUMMARY_CSV,
)

# ── 경로 ──────────────────────────────────────────────────────────────
INPUT_CSV = USERTAGS_SUMMARY_CSV
OUT_DIR   = TAG_ANALYSIS_DIR
os.makedirs(OUT_DIR, exist_ok=True)

# ── 색상 ──────────────────────────────────────────────────────────────
PINK, SKYBLUE = '#FF7EB3', '#7EC8FF'
BG, BG2, BG3  = '#0F0F1A', '#171728', '#1E1E32'
WHITE, GRAY   = '#E8E8F0', '#6A6A88'
GREEN         = '#6BFF9E'
cmap_ps = LinearSegmentedColormap.from_list('ps', ['#FF7EB3','#C890FF','#7EC8FF'], N=256)

plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'axes.unicode_minus': False,
    'text.color': WHITE, 'axes.labelcolor': WHITE,
    'xtick.color': '#B0B0C8', 'ytick.color': '#B0B0C8',
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.spines.left': False, 'axes.spines.bottom': False,
})

# ── 데이터 로드 ────────────────────────────────────────────────────────
df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig')
# appid 컬럼에 '<','=','>' 로 시작하는 행 제거 (CSV 파싱 오류 방어)
for s in ['<','=','>']: df = df[~df['appid'].astype(str).str.startswith(s)]
# 수집 성공 + tags 값이 있는 행만 사용
df_ok = df[(df['success']==True) & df['tags'].notna() & (df['tags']!='')].copy()

# tag_gc: 전체 게임에서 각 태그가 몇 개 게임에 등장했는지 카운트
# tags 컬럼은 JSON 문자열이므로 json.loads() 로 딕셔너리로 변환
tag_gc = Counter()
for ts in df_ok['tags']:
    for tag in json.loads(ts):
        tag_gc[tag] += 1

N = len(df_ok)
print(f'게임 수: {N:,}  |  전체 고유 태그: {len(tag_gc):,}')

# ════════════════════════════════════════════════════════════════════════
# 제외 기준
# ════════════════════════════════════════════════════════════════════════

COV_MAX = 0.70   # 70% 초과 -> 거의 모든 게임이 1, 변별력 없음
COV_MIN = 0.03   # 3% 미만  -> 희소해서 모델 기여 없음

# 플랫폼/인프라 태그: Steam 기능·플레이 방식이지 게임 장르/테마가 아님
TAG_PLATFORM = {
    'Indie','Singleplayer','Multiplayer','Co-op','Online Co-Op','Local Co-Op',
    'Local Multiplayer','Cross-Platform Multiplayer','PvP','PvE',
    'Early Access','Free to Play','Demo',
    'Controller','Partial Controller Support','Full controller support',
    'Steam Achievements','Steam Trading Cards','Steam Workshop',
    'Steam Cloud','Steam Leaderboards','Steam Remote Play',
}

# 감성/사후평가 태그: 게임이 성공한 뒤 유저가 붙이는 경향이 있어
# Y(리뷰 수)와 인과관계가 역전될 수 있음 -> data leakage 위험
TAG_SENTIMENT = {
    'Great Soundtrack','Atmospheric','Cute','Funny','Relaxing','Colorful',
    'Dark','Beautiful','Masterpiece','Memes','Difficult','Addictive',
    'Replay Value','Emotional','Surreal','Minimalist','Experimental',
    'Stylized','Abstract','Nostalgic','Satisfying','Wholesome','Cozy',
    'Immersive','Polished','Well-written','Meaningful Choices','Unique',
    'Complex','Deep','Charming','Captivating','Replayable','Cinematic',
    'Realistic','Moddable','Score Attack','Choices Matter',
}

# 너무 광범위해서 장르 식별력이 없는 태그
TAG_TOO_BROAD = {
    'Action','Adventure','Strategy','Simulation','Casual','Anime',
}

# ── 제외 사유 레이블링 ─────────────────────────────────────────────────
# 각 태그에 대해 제외 사유를 모두 기록 (복수 사유 가능)
# exclude_reason: ' | ' 로 구분된 사유 문자열
rows = []
for tag, cnt in tag_gc.most_common():
    cov     = cnt / N
    reasons = []
    if cov > COV_MAX:           reasons.append(f'cov_high ({cov*100:.1f}%)')
    if cov < COV_MIN:           reasons.append(f'cov_low ({cov*100:.1f}%)')
    if tag in TAG_PLATFORM:     reasons.append('platform_meta')
    if tag in TAG_SENTIMENT:    reasons.append('sentiment_leakage')
    if tag in TAG_TOO_BROAD:    reasons.append('too_broad')
    rows.append({
        'tag'           : tag,
        'game_count'    : cnt,
        'coverage_pct'  : round(cov * 100, 2),
        'excluded'      : bool(reasons),
        'exclude_reason': ' | '.join(reasons),
    })

full_df     = pd.DataFrame(rows)
# selected_df: 제외되지 않은 태그만. index 를 1부터 시작(rank).
selected_df = full_df[~full_df['excluded']].reset_index(drop=True)
selected_df.index += 1

print(f'\n전체 태그: {len(full_df)}  |  제외: {full_df["excluded"].sum()}  |  최종 선정: {len(selected_df)}')
print('\n[최종 선정 태그 상위 30]')
print(selected_df[['tag','coverage_pct']].head(30).to_string())

# ── CSV 저장 ────────────────────────────────────────────────────────────
full_df.to_csv(TAG_EXCLUSION_CSV, index=False, encoding='utf-8-sig')

# index_label='rank': rank 컬럼이 1부터 시작하는 순위
selected_df[['tag','game_count','coverage_pct']].to_csv(
    SELECTED_TAGS_CSV,
    index_label='rank', encoding='utf-8-sig')

print('\nCSV 저장 완료')

# ════════════════════════════════════════════════════════════════════════
# 시각화
# ════════════════════════════════════════════════════════════════════════

fig   = plt.figure(figsize=(24, 28), facecolor=BG)
gspec = gridspec.GridSpec(3, 2, hspace=0.5, wspace=0.35,
                          left=0.07, right=0.96, top=0.93, bottom=0.04)

# ── Chart 1: 전체 태그 커버리지 막대 + 필터 경계선 ───────────────────
ax0 = fig.add_subplot(gspec[0, :])
ax0.set_facecolor(BG2)

sorted_rows = sorted(rows, key=lambda x: -x['coverage_pct'])
cov_vals = [r['coverage_pct'] for r in sorted_rows]
# 선정 태그: GREEN, 제외 태그: 어두운 회색
bar_col  = [GREEN if not r['excluded'] else '#383855' for r in sorted_rows]

ax0.bar(range(len(cov_vals)), cov_vals, width=1.0, color=bar_col, edgecolor='none', alpha=0.9)
ax0.axhline(COV_MAX*100, color=PINK,    linewidth=1.8, linestyle='--', alpha=0.9,
            label=f'Upper bound {int(COV_MAX*100)}%')
ax0.axhline(COV_MIN*100, color=SKYBLUE, linewidth=1.8, linestyle='--', alpha=0.9,
            label=f'Lower bound {int(COV_MIN*100)}%')

ax0.set_xlabel('Tag rank (coverage order)', fontsize=11, color=GRAY)
ax0.set_ylabel('Game Coverage (%)', fontsize=11, color=GRAY)
ax0.set_title('All 448 Tags  -  Coverage Distribution  +  Selection Filter',
              fontsize=15, fontweight='bold', color=WHITE, pad=14)
ax0.set_xlim(-2, len(cov_vals) + 2)
ax0.grid(axis='y', color=BG3, linewidth=0.7)
ax0.set_axisbelow(True)
ax0.legend(handles=[
    mpatches.Patch(color=GREEN,    alpha=0.9,  label=f'Selected  ({len(selected_df)})'),
    mpatches.Patch(color='#383855',alpha=0.9,  label=f'Excluded  ({full_df["excluded"].sum()})'),
    mpatches.Patch(color=PINK,     alpha=0.9,  label=f'Upper {int(COV_MAX*100)}%'),
    mpatches.Patch(color=SKYBLUE,  alpha=0.9,  label=f'Lower {int(COV_MIN*100)}%'),
], loc='upper right', framealpha=0, fontsize=9.5, labelcolor=WHITE)

# ── Chart 2: 제외 사유별 태그 수 ──────────────────────────────────────
ax1 = fig.add_subplot(gspec[1, 0])
ax1.set_facecolor(BG2)

reason_label = {
    'cov_high'          : f'Coverage > {int(COV_MAX*100)}%',
    'cov_low'           : f'Coverage < {int(COV_MIN*100)}%',
    'platform_meta'     : 'Platform / infra tag',
    'sentiment_leakage' : 'Sentiment / post-hoc',
    'too_broad'         : 'Too broad',
}
reason_cnt = {v: 0 for v in reason_label.values()}
for r in rows:
    if r['excluded']:
        for part in r['exclude_reason'].split(' | '):
            key = part.split(' ')[0]
            if key in reason_label:
                reason_cnt[reason_label[key]] += 1

r_labels = list(reason_cnt.keys())
r_vals   = list(reason_cnt.values())
bcolors  = [cmap_ps(i / max(len(r_labels)-1, 1)) for i in range(len(r_labels))]
ax1.barh(r_labels, r_vals, height=0.55, color=bcolors, edgecolor='none', alpha=0.88)
for i, v in enumerate(r_vals):
    ax1.text(v + 0.3, i, str(v), va='center', fontsize=10.5, color=WHITE)
ax1.set_xlabel('Number of excluded tags', fontsize=10, color=GRAY)
ax1.set_title('Exclusion Breakdown by Reason', fontsize=13, fontweight='bold', color=WHITE, pad=10)
ax1.set_yticklabels(r_labels, fontsize=9.5, color=WHITE)
ax1.grid(axis='x', color=BG3)
ax1.set_axisbelow(True)

# ── Chart 3: 최종 선정 태그 상위 50 ───────────────────────────────────
ax2 = fig.add_subplot(gspec[1, 1])
ax2.set_facecolor(BG2)

top_sel = selected_df.head(50)
yp = list(range(len(top_sel)-1, -1, -1))
bc = [cmap_ps(i / (len(top_sel)-1)) for i in range(len(top_sel))]
ax2.barh(yp, list(reversed(top_sel['coverage_pct'].tolist())),
         height=0.7, color=list(reversed(bc)), edgecolor='none', alpha=0.9)
for i, (_, row) in enumerate(reversed(list(top_sel.iterrows()))):
    ax2.text(row['coverage_pct'] + 0.3, i, f'{row["coverage_pct"]:.1f}%',
             va='center', fontsize=7.5, color=GRAY)
ax2.set_yticks(yp)
ax2.set_yticklabels(list(reversed(top_sel['tag'].tolist())), fontsize=8.5, color=WHITE)
ax2.set_xlabel('Game Coverage (%)', fontsize=10, color=GRAY)
ax2.set_title(f'Final Selected Tags  -  Top 50  (total: {len(selected_df)})',
              fontsize=13, fontweight='bold', color=WHITE, pad=10)
ax2.set_xlim(0, top_sel['coverage_pct'].max() * 1.12)
ax2.grid(axis='x', color=BG3)
ax2.set_axisbelow(True)

# ── Chart 4: 선정된 태그의 커버리지 분포 히스토그램 ───────────────────
ax3 = fig.add_subplot(gspec[2, 0])
ax3.set_facecolor(BG2)

sel_cov = selected_df['coverage_pct'].values
cnts, bins, pts = ax3.hist(sel_cov, bins=30, edgecolor='none')
for p2, c2 in zip(pts, cnts):
    r2 = c2 / max(cnts) if max(cnts) > 0 else 0
    p2.set_facecolor((int(255*r2+126*(1-r2))/255,
                      int(126*r2+200*(1-r2))/255,
                      int(179*r2+255*(1-r2))/255))
    p2.set_alpha(0.9)
ax3.axvline(sel_cov.mean(), color=PINK,    linewidth=2, linestyle='--',
            label=f'Mean   {sel_cov.mean():.1f}%')
ax3.axvline(np.median(sel_cov), color=SKYBLUE, linewidth=2, linestyle='-',
            label=f'Median {np.median(sel_cov):.1f}%')
ax3.set_xlabel('Coverage (%)', fontsize=10, color=GRAY)
ax3.set_ylabel('Number of Tags', fontsize=10, color=GRAY)
ax3.set_title('Selected Tags  -  Coverage Distribution',
              fontsize=13, fontweight='bold', color=WHITE, pad=10)
ax3.legend(framealpha=0, fontsize=9.5, labelcolor=WHITE)
ax3.grid(axis='y', color=BG3)
ax3.set_axisbelow(True)

# ── Chart 5: 논문 52개 태그 선정/탈락 현황 ────────────────────────────
# 논문 기준 태그가 우리 데이터셋에서 어떻게 분류됐는지 확인용
ax4 = fig.add_subplot(gspec[2, 1])
ax4.set_facecolor(BG2)

PAPER = [
    '2D','4X','Board Game','Card Game','City Builder','Crafting','Cyberpunk',
    'Dating Sim','Episodic','Family Friendly','Fantasy','Female Protagonist',
    'Fighting','First-Person','Flight','FPS','Hidden Object','Horror','JRPG',
    'Medieval','Noir','Nudity','Open World','Parkour','Pixel Graphics',
    'Platformer','Point & Click','Puzzle','Remake','Retro','Rhythm','Roguelike',
    'Rogue-lite','RTS','Sandbox','Sci-fi','Space','Stealth','Steampunk',
    'Story Rich','Superhero','Survival','Survival Horror','Third Person',
    'Third-Person Shooter','Tower Defense','Turn-Based','Turn-Based Strategy',
    'Visual Novel','Walking Simulator','World War II','Zombies'
]

paper_result = []
for pt in PAPER:
    match = full_df[full_df['tag'].str.lower() == pt.lower()]
    if len(match) == 0:
        cov = 0; status = 'not_found'
    else:
        r = match.iloc[0]
        if not r['excluded']:
            status = 'selected'
        else:
            status = r['exclude_reason'].split(' ')[0]
        cov = r['coverage_pct']
    paper_result.append({'tag': pt, 'cov': cov, 'status': status})

pr_df = pd.DataFrame(paper_result).sort_values('cov', ascending=True)
status_color = {
    'selected'          : GREEN,
    'cov_low'           : SKYBLUE,
    'cov_high'          : PINK,
    'platform_meta'     : '#888888',
    'sentiment_leakage' : '#FFAA44',
    'too_broad'         : '#CC88FF',
    'not_found'         : '#444444',
}
ax4.barh(range(len(pr_df)), pr_df['cov'],
         height=0.7, color=[status_color.get(s, '#888888') for s in pr_df['status']],
         edgecolor='none', alpha=0.88)
ax4.set_yticks(range(len(pr_df)))
ax4.set_yticklabels(pr_df['tag'], fontsize=7.8, color=WHITE)
ax4.set_xlabel('Coverage (%)', fontsize=10, color=GRAY)
ax4.set_title("Paper's 52 Tags  -  Selected vs Excluded in Our Dataset",
              fontsize=13, fontweight='bold', color=WHITE, pad=10)
ax4.grid(axis='x', color=BG3)
ax4.set_axisbelow(True)
ax4.legend(handles=[mpatches.Patch(color=v, alpha=0.88, label=k)
                    for k, v in status_color.items()],
           loc='lower right', framealpha=0, fontsize=8, labelcolor=WHITE)

# ── 전체 타이틀 ───────────────────────────────────────────────────────
fig.text(0.5, 0.965, 'Steam User Tags  -  Feature Selection Report',
         ha='center', va='top', fontsize=21, fontweight='bold', color=WHITE)
fig.text(0.5, 0.950,
         f'Total: {len(full_df)}  ->  Excluded: {full_df["excluded"].sum()}  ->  Selected: {len(selected_df)}  '
         f'|  Filter: {int(COV_MIN*100)}% <= coverage <= {int(COV_MAX*100)}%  +  platform / sentiment / too_broad',
         ha='center', va='top', fontsize=10.5, color=GRAY)

plt.savefig(TAG_SELECTION_REPORT_PNG, dpi=160, bbox_inches='tight', facecolor=BG)

print('시각화 저장 완료')
print(f'\n최종 선정 태그 수: {len(selected_df)}')
print('-> 05_selected_tags_final.csv 를 08_feature_engineering.py 에서 사용합니다.')
