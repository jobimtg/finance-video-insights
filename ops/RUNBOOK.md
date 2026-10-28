# 財經影片統整｜排程作業手冊（給排程啟動的 Claude 工作階段）

本檔不含任何金鑰或個人資料。完整規則以 skill「finance-video-insights」為準；本檔只寫排程作業的固定步驟。
時間一律用溫哥華時間（全年 UTC-7），格式「年-月-日 時:分」。需要使用者決定的事，一律用選擇題（AskUserQuestion）；使用者不在時用 PushNotification 通知並停下。

## 0. 環境準備（每次新工作階段都要做）
```
cd /home/claude 2>/dev/null || cd ~
[ -d finance-video-insights ] || env -u GH_TOKEN git clone https://github.com/jobimtg/finance-video-insights
cd finance-video-insights && git pull -q
git config user.name jobimtg && git config user.email jobimtg@users.noreply.github.com
mkdir -p ~/tools && cp ops/ghrun.sh ~/tools/ghrun.sh && chmod +x ~/tools/ghrun.sh
```
- GitHub API 一律 `env -u GH_TOKEN`。commit 訊息結尾加上系統提示指定的署名行。
- workflow：產出報告草稿 388081674（`{"date":"YYYYMMDD"}`）、發布報告 388081676（`{"date":"YYYYMMDD","send_line":"false"}`）、獨立重抓比對（Agent 4）388310888、名稱核對 388301182（`{"items":"名稱:代號 …"}`）。
- 執行方式：`~/tools/ghrun.sh <workflow id> '<json>'`，會等待完成並印出結果。

## 1. 每日 20:00：讀逐字稿與整理觀點（週一至週五）
1. 從 `data/uploads.json` 取當天（YYYYMMDD）上、中、下集影片 ID；沒有就用內建瀏覽器開頻道 RSS（channel_id=UC_ObC9O0ZQ2FhW6u9_iFlZA）找「YYYYMMDD完整版(上/中/下集)」。
   - 2026-10-26 經使用者同意：當天只有「YYYYMMDD完整版(全集)」一支時，視為完整一集（uploads.json 記為「全」），Agent 1 確認全集結尾完整即可；ts 用「全 mm:ss」。RSS 回 404 時改用 YouTube 搜尋或頻道影片頁。
2. 內建瀏覽器：ToolSearch 載入 `mcp__remote-devices__Claude_Browser__navigate`、`mcp__remote-devices__Claude_Browser__javascript_tool`。只讀取，影片靜音、讀完暫停，不改動使用者電腦任何檔案。
   - 方法一（字幕檔，較穩）：見本檔附錄 A 程式。
   - 方法二（逐字稿面板）：附錄 B 程式。
   - 當天頻道沒有「YYYYMMDD完整版」影片（停播、颱風假或休市）：在 Notion 記錄「當天無完整版影片」，不通知、不重試，直接結束。
   - 電腦連不上或兩種方法都失敗：不要重試超過 1 次；用 PushNotification 通知使用者，請他打開電腦上的 Claude 桌面 app 或貼上逐字稿，然後停下。
3. 依 skill 步驟 2 寫 `episodes/YYYYMMDD/episode.json`（參考前幾集格式）：
   - guests 為來賓名單；背景股不放 segments；每段 2–10 檔；族群用半形斜線。
   - 節目已給數字就不另加 derive；季線若來賓明說 65 日就用 ma65。
   - 來賓自行推算的價格只寫在觀點，目標價欄只收節目明確說出的機構或法人目標價。
   - 原油採節目口述價（source text）；只有該集有原油項目才會出現布蘭特說明。
   - 主持人帶出的說法要標主持人；觀點用改寫摘要，不逐字照抄。
4. 名稱核對（388301182），market 依結果設定。推上 repo。
5. 用新的 subagent 跑 Agent 1、3（自行用內建瀏覽器重讀逐字稿），依結果修正後推上 repo。
6. 週五：完成後接著做第 3 節週報。

- 2026-10-26 經使用者同意：播出日休市（例如補假）時，影片當日收盤改用播出日前最後一個交易日收盤（build_report.py 自動處理，表格說明列註明），驗證日仍從播出日起算。

## 2. 每日 03:30：產出與發布前一集（週一至週五）
- 對象：已有 episode.json、但 `docs/reports/` 還沒有該集 PDF、且播出日之後已有至少 1 個交易日收盤的集數（週一處理上週五那集）。
1. 產出報告草稿（388081674）。確認絕大多數個股 latest_date 為最新交易日、初檢通過、頁數 5–9。
   - FinMind 每小時 600 次上限：若 HTTPError，1 小時後再試。資料停在舊日期：2 小時後再試。同一問題 2 次仍失敗就通知使用者並停下。
2. 看 PDF 第 1–3 頁；跑 Agent 4（388310888）；用新 subagent 跑 Agent 5–7（skill 檔＋repo scripts/render_report.py 為準）。
- 2026-10-27 經使用者同意（選項 A）：臨時休市（平日但加權指數沒有資料，例如 10/23 颱風假）也算休市，2／5／20 日驗證日一併扣除（build_report.py 自動處理，產出紀錄會列出）。
3. 全部通過才發布（388081676，send_line "false"）。**每日報告不推 LINE**（2026-10-21 定案）。
4. 更新 Notion「財經影片統整」頁（id 3f95a561-5413-8182-9778-ce7f5d893622）：做了什麼、檢查結果、未完成事項。

## 3. 週五 21:00：週報摘要（2026-10-23 版面定案）
- 範圍：本週一～週五各集；週五那集的播出後漲跌與驗證標「下週更新」。
- 內容：本週重點、各集一覽與完整版連結、加權指數、驗證統計、下週事件、播出後漲跌排行、族群表現、多集重複點名個股；5–9 頁（當週少於 5 集時可 3–9 頁）；只推這一則 LINE。
- 步驟：確認週五那集已有 episode.json（20:00 作業完成）；對週五那集執行「產出報告草稿」（初檢會因尚無播出後交易日而不通過，屬正常，只用來提供週報資料）；執行 workflow「週報摘要」（weekly-report.yml，inputs：week_end=週五 YYYYMMDD、send_line=true）；看 PDF；更新 Notion。

## 附錄 A：字幕檔讀取
```
await new Promise(r=>setTimeout(r,3000));
const VID=new URL(location.href).searchParams.get('v');
const p=document.querySelector('#movie_player'); try{p.mute(); p.playVideo(); p.loadModule('captions'); p.setOption('captions','track',{languageCode:'zh-Hant'});}catch(e){}
document.querySelector('.ytp-subtitles-button[aria-pressed="false"]')?.click();
let u=null; for(let i=0;i<20;i++){ await new Promise(r=>setTimeout(r,1000)); const e=performance.getEntriesByType('resource').map(x=>x.name).filter(n=>n.includes('/api/timedtext')&&n.includes('pot=')&&n.includes(VID)); if(e.length){u=e[e.length-1];break;} }
let out=''; if(u){ const r=await fetch(u.replace(/&fmt=[^&]*/,'')+'&fmt=json3'); const j=await r.json(); let buf=[],st=null; for(const e of (j.events||[]).filter(e=>e.segs)){ const s=Math.floor(e.tStartMs/1000); if(st===null||s-st>=15){ if(buf.length) out+=Math.floor(st/60)+':'+String(st%60).padStart(2,'0')+' '+buf.join(' ')+'\n'; buf=[]; st=s;} buf.push(e.segs.map(x=>x.utf8).join('').replace(/\n/g,' ')); } if(buf.length) out+=Math.floor(st/60)+':'+String(st%60).padStart(2,'0')+' '+buf.join(' '); }
try{p.pauseVideo()}catch(e){}
(u?'ok ':'none ')+' len='+window.ytInitialPlayerResponse?.videoDetails?.lengthSeconds+'\n'+out
```

## 附錄 B：逐字稿面板讀取
```
let b=[]; for(let i=0;i<15;i++){ await new Promise(r=>setTimeout(r,1000)); b=[...document.querySelectorAll('ytd-video-description-transcript-section-renderer button')]; if(b.length) break;}
b.forEach(x=>x.click());
await new Promise(r=>setTimeout(r,3000));
const chip=[...document.querySelectorAll('button, yt-chip-cloud-chip-renderer, chip-shape')].find(e=>/^\s*(Transcript|轉錄稿|逐字稿)\s*$/.test(e.innerText||'')); if(chip) chip.click();
let segs=[]; for(let i=0;i<20;i++){ await new Promise(r=>setTimeout(r,1000)); segs=document.querySelectorAll('ytd-transcript-segment-renderer, transcript-segment-view-model'); if(segs.length) break;}
try{document.querySelector('#movie_player').pauseVideo()}catch(e){}
b.length+' '+segs.length+' len='+window.ytInitialPlayerResponse?.videoDetails?.lengthSeconds+'\n'+[...segs].map(s=>s.innerText.replace(/\s+/g,' ').trim().replace(/^(\d+:\d+(?::\d+)?) .*?(seconds?|minutes?|hours?) /,'$1 ')).join('\n')
```
