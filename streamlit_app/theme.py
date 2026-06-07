"""Shared CSS for the Clipsay Streamlit console.

All selectors are namespaced under ``.clipsay-`` (or ``#clipsay-`` for ids)
so they don't collide with Streamlit's own internals.
"""


GLOBAL_CSS = """
.main > .block-container { padding-top:0 !important; }
[data-testid="stAppViewBlockContainer"] { padding-top:0 !important; }
[data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:first-child [data-testid="stHeading"] { margin-top:0 !important; }
h1:first-of-type { margin-top:0 !important; }
[data-testid="stSidebar"] { min-width:auto !important; width:auto !important; flex:0 0 auto !important; }
[data-testid="stSidebarContent"] { width:auto !important; min-width:0 !important; }
button[data-testid="collapsedControl"] { display:none !important; }
"""


CLIP_GRID_CSS = """
.clipsay-grid {
  display:grid; grid-template-columns:repeat(3,1fr); gap:16px;
  width:100%; max-width:1200px; margin:24px auto 0; padding:0 16px 16px;
}
.clipsay-item { display:flex; flex-direction:column; }
.clipsay-cell {
  text-decoration:none; display:block; border-radius:10px; overflow:hidden;
  aspect-ratio:16/9; position:relative;
  transition:transform .2s ease, box-shadow .2s ease;
}
.clipsay-cell:hover { transform:scale(1.02); box-shadow:0 4px 20px rgba(0,0,0,.4); }
.clipsay-cell-new { border:1.5px dashed rgba(151,166,195,0.25); border-radius:10px; background:rgba(151,166,195,0.06); }
.clipsay-thumb { width:100%; height:100%; display:flex; align-items:center; justify-content:center; position:relative; }
.clipsay-play {
  position:absolute; width:48px; height:48px; border-radius:50%;
  background:rgba(0,0,0,.55); display:flex; align-items:center; justify-content:center;
  z-index:2; transition:background .2s;
}
.clipsay-cell:not(.clipsay-cell-new) .clipsay-play { font-size:28px; color:#fff; line-height:1; }
.clipsay-cell-new .clipsay-play { font-size:28px; font-weight:300; color:#fff; line-height:1; }
.clipsay-cell:hover .clipsay-play { background:rgba(255,75,75,.85); }
.clipsay-cell-new:hover { border-color:rgba(255,75,75,0.4); }
.clipsay-meta { display:flex; align-items:center; gap:6px; margin-top:6px; padding:0 2px; }
.clipsay-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.clipsay-dot.new { background:rgba(255,255,255,0.8); }
.clipsay-dot.cancel { background:#888; }
.clipsay-dot.progress { background:#ff4b4b; }
.clipsay-dot.stop { background:#f0c000; }
.clipsay-dot.success { background:#00c853; }
.clipsay-title {
  font-size:13px; color:rgb(200,200,210);
  overflow:hidden; text-overflow:ellipsis;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
  word-break:break-word;
}
"""


SETTINGS_PANEL_CSS = """
.clipsay-settings-label {
  position:fixed; top:16px; right:200px; z-index:999990;
  background:rgba(151,166,195,0.1); border:0 none;
  font-size:14px; font-weight:400; height:28px; line-height:28px;
  padding:0 8px; border-radius:8px;
  display:inline-flex; align-items:center;
  color:rgb(250,250,250); cursor:pointer;
  font-family:-apple-system,BlinkMacSystemFont,sans-serif;
}
.clipsay-settings-label:hover { background:rgba(151,166,195,0.15); }
.clipsay-backdrop {
  display:none; position:fixed; top:0; left:0; width:100%; height:100%;
  background:rgba(0,0,0,0.5); z-index:999992; cursor:default;
}
.clipsay-popup {
  display:none; position:fixed; top:80px; left:50%;
  transform:translateX(-50%); z-index:999993;
  background:rgb(14,17,23); border-radius:16px; padding:0 0 24px;
  width:900px; max-width:90vw; overflow:visible;
  font-family:-apple-system,BlinkMacSystemFont,sans-serif;
  color:rgb(250,250,250);
}
.clipsay-popup-header {
  display:flex; justify-content:space-between; align-items:center;
  padding:20px 24px 12px; font-size:20px; font-weight:600;
  border-bottom:1px solid rgba(151,166,195,0.2);
}
.clipsay-popup-grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; padding:4px 24px; }
.clipsay-popup-close {
  cursor:pointer; font-size:24px; color:rgb(163,168,184); text-decoration:none;
  padding:0 4px; border-radius:4px; border:none; background:none;
}
.clipsay-popup-close:hover { color:rgb(250,250,250); }
.clipsay-card {
  display:flex; flex-direction:column; gap:8px;
  padding:16px; border-radius:12px;
  border:1px solid rgba(151,166,195,0.2);
}
.clipsay-card-header { display:flex; justify-content:space-between; align-items:flex-start; }
.clipsay-card-title { font-size:15px; font-weight:600; }
.clipsay-card-desc { font-size:12px; color:rgb(163,168,184); margin-bottom:6px; }
.clipsay-field { display:flex; flex-direction:column; gap:3px; margin-bottom:6px; }
.clipsay-field span { font-size:11px; color:rgba(151,166,195,0.6); text-transform:uppercase; letter-spacing:0.5px; }
.clipsay-model { display:flex; flex-direction:column; gap:3px; margin-bottom:6px; }
.clipsay-model span { font-size:11px; color:rgba(151,166,195,0.6); text-transform:uppercase; letter-spacing:0.5px; }
.clipsay-input {
  width:100%; padding:5px 8px; border-radius:6px; border:1px solid rgba(151,166,195,0.2);
  background:rgba(0,0,0,0.3); color:rgb(250,250,250); font-size:12px;
  box-sizing:border-box; outline:none;
}
.clipsay-input:focus { border-color:rgb(255,75,75); }
.clipsay-select {
  width:100%; padding:5px 8px; border-radius:6px; border:1px solid rgba(151,166,195,0.2);
  background:rgba(0,0,0,0.3); color:rgb(250,250,250); font-size:12px;
  box-sizing:border-box; outline:none; cursor:pointer;
}
.clipsay-select:focus { border-color:rgb(255,75,75); }
.clipsay-ratelimit { display:flex; flex-direction:column; gap:4px; margin-bottom:6px; }
.clipsay-ratelimit > span { font-size:11px; color:rgba(151,166,195,0.6); text-transform:uppercase; letter-spacing:0.5px; }
.clipsay-rl-inline { display:flex; gap:6px; }
.clipsay-rl-row { display:flex; align-items:center; gap:3px; flex:1; }
.clipsay-rl-row span { font-size:11px; color:rgba(151,166,195,0.6); white-space:nowrap; }
.clipsay-rl-row input { flex:1; min-width:0; }
.clipsay-card-spacer { flex:1; }
.clipsay-btns { display:flex; gap:6px; margin-top:14px; }
.clipsay-btn {
  flex:1; padding:6px 12px; border-radius:8px; cursor:pointer;
  border:none; font-size:13px; font-weight:600; text-align:center;
  color:rgb(250,250,250);
}
.clipsay-btn-save { background:rgb(255,75,75); }
.clipsay-btn-save:hover { background:rgb(235,55,55); }
#clipsay-settings-toggle:checked ~ .clipsay-backdrop { display:block !important; }
#clipsay-settings-toggle:checked ~ .clipsay-popup { display:block !important; }
"""


PRODUCTION_CSS = """
[data-testid="stTextArea"] { margin-bottom:0; background:transparent !important; border:none !important; padding:0 !important; }
[data-testid="stTextArea"] textarea {
  height:52px !important; padding:10px 14px; box-sizing:border-box !important;
  min-height:52px !important; max-height:52px !important;
  border-radius:10px; border:1px solid rgba(151,166,195,0.2);
  background:rgba(0,0,0,0.3); color:rgb(250,250,250); font-size:14px; resize:none;
  outline:none; font-family:inherit;
}
[data-testid="stTextArea"] textarea:focus { border-color:rgb(255,75,75); }
.prod-wrap { max-width:1100px; margin:0 auto; }
.prod-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; }
.prod-header h2 { margin:0; font-size:22px; }
.prod-header .prod-status { font-size:13px; color:#888; }
.prod-timeline {
  background:rgba(255,255,255,0.03); border:1px solid rgba(151,166,195,0.1);
  border-radius:10px; padding:20px 24px;
  display:flex; align-items:center; gap:0; flex:1;
}
.prod-step { flex:1; display:flex; flex-direction:column; align-items:center; position:relative; }
.prod-step:not(:last-child)::after {
  content:''; position:absolute; top:14px; left:50%; width:100%; height:2px;
  background:rgba(151,166,195,0.08); z-index:0;
}
.prod-step.active:not(:last-child)::after,
.prod-step.complete:not(:last-child)::after { background:rgba(255,75,75,0.5); }
.prod-step.complete:not(:last-child)::after { background:#ff4b4b; }
.prod-dot {
  width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center;
  position:relative; z-index:1; font-size:11px; font-weight:700;
  border:2px solid rgba(151,166,195,0.15); color:#fff;
  background:transparent; transition:all .3s ease;
}
.prod-step.complete .prod-dot { background:#ff4b4b; border-color:#ff4b4b; color:#fff; box-shadow:0 0 0 1px rgba(255,75,75,0.2); }
.prod-step.active .prod-dot { border-color:#ff4b4b; color:#fff; box-shadow:inset 0 0 0 2px rgba(255,75,75,0.15); }
.prod-step-label {
  font-size:11px; margin-top:8px; color:rgba(151,166,195,0.4);
  font-weight:500; letter-spacing:0.3px; text-transform:uppercase;
  transition:color .3s;
}
.prod-step.complete .prod-step-label { color:#ff4b4b; }
.prod-step.active .prod-step-label { color:rgb(250,250,250); }
.prod-timeline-row { display:flex; align-items:stretch; gap:12px; margin-bottom:20px; }
.prod-cards { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:16px; }
.prod-card {
  padding:18px; border-radius:12px; border:1px solid rgba(151,166,195,0.15);
  background:rgba(255,255,255,0.03);
}
.prod-card h4 { margin:0 0 8px; font-size:14px; display:flex; align-items:center; gap:8px; }
.prod-card-hdr { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }
.prod-card-hdr h4 { margin:0; font-size:14px; display:flex; align-items:center; gap:8px; }
.prod-card-actions { display:flex; gap:4px; }
.prod-card-btn {
  padding:2px 10px; border-radius:6px; border:none; font-size:11px; font-weight:600;
  cursor:pointer; transition:background .2s;
}
.prod-card-btn.gen { background:rgba(255,75,75,0.15); color:#ff4b4b; }
.prod-card-btn.gen:hover { background:rgba(255,75,75,0.25); }
.prod-card-btn.edit { background:rgba(151,166,195,0.1); color:rgb(163,168,184); }
.prod-card-btn.edit:hover { background:rgba(151,166,195,0.2); }
.prod-card p { margin:0; font-size:13px; color:#999; line-height:1.5; }
.prod-card ul { margin:0; padding-left:20px; font-size:13px; color:#999; line-height:1.5; }
.prod-card li { margin:0; }
.portraits-grid { display:flex; flex-direction:column; gap:12px; }
.portrait-row { display:flex; gap:12px; }
.portrait-cell { flex:1; display:flex; flex-direction:column; gap:4px; }
.portrait-name { font-size:12px; color:#ccc; }
.portrait-views { display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; }
.portrait-thumb { width:100%; aspect-ratio:1/1; object-fit:cover; border-radius:6px; border:1px solid rgba(151,166,195,0.15); }
@keyframes portrait-spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
.portrait-skeleton {
  width:100%; aspect-ratio:1/1; border-radius:6px;
  background: rgba(151,166,195,0.1);
  display:flex; align-items:center; justify-content:center;
  border:1px solid rgba(151,166,195,0.1);
}
.portrait-skeleton-spinner {
  width:14px; height:14px; border:2px solid rgba(151,166,195,0.2);
  border-top-color:rgba(151,166,195,0.5); border-radius:50%;
  animation: portrait-spin 0.8s linear infinite;
}
.portraits-loading-text { font-size:11px; color:#777; margin-top:8px; text-align:center; }
.prod-card .prod-tag {
  display:inline-block; font-size:11px; padding:2px 8px; border-radius:4px;
  background:rgba(255,75,75,0.1); color:#ff4b4b; margin-top:8px;
}
.prod-meta-row { display:flex; gap:16px; margin-bottom:24px; flex-wrap:wrap; }
.prod-meta-item { font-size:12px; color:#888; }
.prod-meta-item strong { color:#ccc; }
.prod-story-block {
  background:rgba(255,255,255,0.03); border:1px solid rgba(151,166,195,0.1);
  border-radius:10px; padding:16px 20px; margin-bottom:20px;
}
.prod-story-block h4 { margin:0 0 10px; font-size:14px; color:#ff4b4b; }
.prod-story-block p { margin:0; font-size:13px; color:#bbb; line-height:1.6; white-space:pre-wrap; }
"""
