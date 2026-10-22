/* Home Share — original, dependency-free Home Assistant panel. MIT licensed. */
const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const icon = (name, size=21) => `<ha-icon icon="mdi:${name}" style="--mdc-icon-size:${size}px"></ha-icon>`;
const domainIcon = {light:"lightbulb-outline",switch:"power-socket-us",climate:"thermostat",sensor:"chart-line",fan:"fan",cover:"blinds",valve:"valve",media_player:"speaker",lock:"lock-outline",camera:"video-outline",vacuum:"robot-vacuum",scene:"palette-outline",script:"script-text-outline"};

class HomeSharePanel extends HTMLElement {
  constructor() {
    super(); this.attachShadow({mode:"open"}); this.drafts={}; this.selected=new Set();
    this.filter="shared"; this.search=""; this.area=""; this.focusId=null; this.busy=false;
  }
  set hass(value) {
    this._hass=value;
    this.toggleAttribute("dark",!!value.themes?.darkMode);
    if (!this.started && this.isConnected) { this.started=true; this.load(); this.subscribe(); }
  }
  connectedCallback() {
    if(this._hass && !this.started) {this.started=true; this.load(); this.subscribe();}
    if(this.data) this.render();
  }
  disconnectedCallback() { if(this.unsubscribe) this.unsubscribe(); this.unsubscribe=null; this.started=false; }
  async subscribe() {
    try { const unsubscribe=await this._hass.connection.subscribeEvents(()=>{
      if(!this.busy) {if(Object.keys(this.drafts).length) { this.external=true; this.renderBar(); } else this.load();}
    },"home_share_updated"); if(this.isConnected) this.unsubscribe=unsubscribe; else unsubscribe(); } catch { /* Manual refresh remains available. */ }
  }
  async api(action, extra={}) { return this._hass.callWS({type:"home_share/manage",action,...extra}); }
  async load() {
    try {this.data=await this.api("list"); this.error=""; this.external=false; this.render();}
    catch(e) {this.error=e.message || String(e); this.render();}
  }
  item(id) { const item=this.data.items.find(x=>x.entity_id===id), draft=this.drafts[id]||{}; return {...item,google_name:Object.hasOwn(draft,"name")?(draft.name||""):item.google_name,room:Object.hasOwn(draft,"room")?(draft.room||""):item.room,aliases:draft.aliases??item.aliases,shared:draft.expose??item.shared}; }
  draft(id,field,value) {
    const original=this.data.items.find(x=>x.entity_id===id);
    const old=field==="expose"?original.shared:field==="name"?original.google_name:original[field];
    this.drafts[id] ||= {};
    const normalize=v=>field==="expose"?!!v:field==="aliases"?(v||[]):(v||"");
    if(JSON.stringify(normalize(value))===JSON.stringify(normalize(old))) delete this.drafts[id][field];
    else this.drafts[id][field]=value;
    if(!Object.keys(this.drafts[id]).length) delete this.drafts[id];
    this.renderBar();
  }
  visible() {
    const q=this.search.toLowerCase().trim();
    return this.data.items.filter(original=>{
      const item=this.item(original.entity_id);
      return (this.filter==="all" || this.filter==="shared" && item.shared || this.filter==="private" && !item.shared || this.filter==="unavailable" && !item.available && item.configured)
        && (!this.area || item.area===this.area)
        && (!q || `${item.name} ${item.google_name} ${item.entity_id} ${item.room} ${item.area} ${item.aliases.join(" ")}`.toLowerCase().includes(q));
    }).sort((a,b)=>(a.room||a.area).localeCompare(b.room||b.area) || a.name.localeCompare(b.name));
  }
  render() {
    this.shadowRoot.innerHTML=`<style>${styles}</style><div class="app">
      <header><div class="brand"><img class="brand-logo" src="/home_share_static/home-share-mark.svg?v=0.1.3" alt="Home Share logo" width="44" height="44"><span>Home Share <small>FOR GOOGLE HOME</small></span></div><div class="header-actions"><button class="icon" id="menu" aria-label="Open Home Assistant menu">${icon("menu")}</button><button id="history">${icon("history",18)}<span>History</span></button><button id="refresh" class="icon" aria-label="Refresh">${icon("refresh")}</button></div></header>
      <main><div class="hero"><div><div class="eyebrow">YOUR HOME, ON YOUR TERMS</div><h1>A little more connected.</h1><p>Choose what Google Home can see. Make it feel like home.</p></div><div class="connection"><i></i>Live connection<span>No restart needed</span></div></div>
      ${this.error?`<div class="notice error" role="alert">${esc(this.error)} <button id="retry">Try again</button></div>`:""}
      ${!this.data?`<div class="empty">${this.error?"":"Connecting to your home…"}</div>`:`
      <section class="overview" aria-label="Sharing summary"><div><span class="stat">${this.data.stats.shared}</span><span>shared with Google</span></div><div><span class="stat">${this.data.stats.total}</span><span>devices & entities</span></div><div><span class="stat">${this.data.stats.unavailable}</span><span>shared · unavailable</span></div><button id="sync" class="sync">${icon("sync",19)} Sync Google</button></section>
      ${this.data.last_sync?`<div class="sync-result ${this.data.last_sync.ok?"":"warning"}" role="status">${icon(this.data.last_sync.ok?"check-circle-outline":"alert-circle-outline",16)} ${esc(this.data.last_sync.message)}</div>`:""}
      <div class="workspace"><section class="collection"><div class="toolbar"><div class="search">${icon("magnify",20)}<input id="search" placeholder="Find a device, room or alias…" aria-label="Search devices" value="${esc(this.search)}"></div><select id="areas" aria-label="Filter by Home Assistant area"><option value="">All areas</option>${[...new Set(this.data.items.map(x=>x.area))].sort().map(a=>`<option ${a===this.area?"selected":""}>${esc(a)}</option>`).join("")}</select></div><div class="filters" role="group" aria-label="Filter devices">${[["shared","Shared"],["all","All devices"],["private","Not shared"],["unavailable","Unavailable"]].map(([key,label])=>`<button data-filter="${key}" class="${this.filter===key?"active":""}" aria-pressed="${this.filter===key}">${label}</button>`).join("")}</div><div id="bulk"></div><div id="list"></div></section><aside id="detail" aria-label="Device settings"></aside></div>`}
      <footer>Your existing Google connection. A simpler way to manage it.<span>Home Share · 0.1.3</span></footer></main><div id="bar"></div><div id="toast"></div><div id="modal"></div></div>`;
    const $=s=>this.shadowRoot.querySelector(s);
    $("#menu").onclick=()=>this.dispatchEvent(new CustomEvent("hass-toggle-menu",{bubbles:true,composed:true}));
    $("#refresh").onclick=()=>this.refresh(); $("#retry")?.addEventListener("click",()=>this.load());
    $("#history").onclick=()=>this.history();
    if(!this.data) return;
    $("#sync").onclick=()=>this.runSync();
    $("#search").oninput=e=>{this.search=e.target.value;this.renderList();};
    $("#areas").onchange=e=>{this.area=e.target.value;this.renderList();};
    this.shadowRoot.querySelectorAll("[data-filter]").forEach(button=>button.onclick=()=>{
      this.filter=button.dataset.filter;this.shadowRoot.querySelectorAll("[data-filter]").forEach(x=>{x.classList.toggle("active",x===button);x.setAttribute("aria-pressed",x===button);});this.renderList();
    });
    this.renderList(); this.renderDetail(); this.renderBar();
  }
  renderList() {
    const list=this.shadowRoot.querySelector("#list"); if(!list)return;
    const items=this.visible(); let group=null;
    list.innerHTML=items.length?items.map(original=>{
      const x=this.item(original.entity_id), room=x.room||x.area;
      const heading=group!==room?`<h2>${esc(room)}<span>${items.filter(i=>(i.room||i.area)===room).length}</span></h2>`:"";group=room;
      return `${heading}<div class="row ${this.focusId===x.entity_id?"chosen":""} ${this.drafts[x.entity_id]?"edited":""}" data-id="${esc(x.entity_id)}"><input type="checkbox" class="select-row" aria-label="Select ${esc(x.name)}" ${this.selected.has(x.entity_id)?"checked":""}><button class="device" data-open><span class="device-icon ${x.shared?"on":""}">${icon(domainIcon[x.domain]||"shape-outline")}</span><span class="device-copy"><strong>${esc(x.google_name||x.name)}</strong><small>${esc(x.domain.replaceAll("_"," "))}${!x.available?`<span class="offline">${x.disabled?"Disabled":"Unavailable"}</span>`:""}${this.drafts[x.entity_id]?`<span class="draft-dot">Edited</span>`:""}</small></span>${icon("chevron-right",18)}</button><button class="toggle ${x.shared?"on":""}" role="switch" aria-checked="${x.shared}" aria-label="Share ${esc(x.name)} with Google Home" data-toggle><span></span></button></div>`;
    }).join(""):`<div class="empty">${icon("magnify",32)}<h3>No devices here</h3><p>Try a different filter or search.</p></div>`;
    list.querySelectorAll(".row").forEach(row=>{
      const id=row.dataset.id;
      row.querySelector("[data-open]").onclick=()=>{this.focusId=id;this.renderList();this.renderDetail();};
      row.querySelector("[data-toggle]").onclick=()=>{this.draft(id,"expose",!this.item(id).shared);this.renderList();this.renderDetail();};
      row.querySelector(".select-row").onchange=e=>{if(e.target.checked)this.selected.add(id);else this.selected.delete(id);this.renderBulk();};
    });this.renderBulk();
  }
  renderBulk() {
    const el=this.shadowRoot.querySelector("#bulk");if(!el)return;
    el.innerHTML=this.selected.size?`<div class="bulk"><strong>${this.selected.size} selected</strong><button data-share>Share</button><button data-private>Stop sharing</button><button data-clear class="icon" aria-label="Clear selection">${icon("close",18)}</button></div>`:`<div class="list-caption"><span>${this.visible().length} results</span><button data-select>Select visible</button></div>`;
    el.querySelector("[data-select]")?.addEventListener("click",()=>{this.visible().forEach(x=>this.selected.add(x.entity_id));this.renderList();});
    el.querySelector("[data-clear]")?.addEventListener("click",()=>{this.selected.clear();this.renderList();});
    for(const [selector,value] of [["[data-share]",true],["[data-private]",false]]) el.querySelector(selector)?.addEventListener("click",()=>{this.selected.forEach(id=>this.draft(id,"expose",value));this.selected.clear();this.renderList();this.renderDetail();});
  }
  renderDetail() {
    const el=this.shadowRoot.querySelector("#detail");if(!el)return;
    const original=this.data.items.find(x=>x.entity_id===this.focusId);
    el.classList.toggle("open",!!original);
    if(!original){el.innerHTML=`<div class="detail-empty"><span>${icon("tune-variant",30)}</span><h3>Make it yours.</h3><p>Select a device to give it a familiar name, a room and the words you use every day.</p><div class="live-note">${icon("lightning-bolt-outline",18)} Changes apply without restarting Home Assistant.</div></div>`;return;}
    const x=this.item(this.focusId), settings={...this.data.config[x.entity_id],...this.drafts[x.entity_id]};
    el.innerHTML=`<div class="detail-head"><span>DEVICE SETTINGS</span><button class="icon" id="close-detail" aria-label="Close device settings">${icon("close",18)}</button></div><div class="detail-title"><span class="big-icon">${icon(domainIcon[x.domain]||"shape-outline",30)}</span><h2>${esc(original.name)}</h2><span class="status ${x.available?"":"offline"}">${x.available?"Available":x.disabled?"Disabled in Home Assistant":"Currently unavailable"}</span></div><div class="detail-body"><label class="share-field">Share with Google Home<input id="detail-share" type="checkbox" ${x.shared?"checked":""}></label>${!x.available?`<p class="hint retained">Your saved settings are retained. Google can discover this device when Home Assistant provides it again.</p>`:""}<label for="google-name">Name in Google Home</label><input id="google-name" value="${esc(settings.name||"")}" placeholder="${esc(original.name)}" maxlength="255"><p class="hint">Leave blank to use the Home Assistant name.</p><label for="google-room">Room in Google Home</label><input id="google-room" list="rooms" value="${esc(settings.room||"")}" placeholder="Use Home Assistant area" maxlength="255"><datalist id="rooms">${[...new Set(this.data.items.flatMap(i=>[i.room,i.area]).filter(a=>a&&a!=="Unassigned"))].sort().map(a=>`<option value="${esc(a)}"></option>`).join("")}</datalist><p class="hint">Suggests a room when Google first adds a device. Existing Google room assignments may take priority.</p><label for="google-aliases">Other names</label><textarea id="google-aliases" placeholder="Reading lamp&#10;My favorite light" rows="3">${esc((settings.aliases||[]).join("\n"))}</textarea><p class="hint">One name per line. For the words that come naturally.</p><details><summary>Home Assistant details</summary><code>${esc(x.entity_id)}</code><p>${esc(x.area)} · ${esc(x.state??"No state")}</p></details></div>`;
    el.querySelector("#close-detail").onclick=()=>{this.focusId=null;this.renderDetail();this.renderList();};
    el.querySelector("#detail-share").onchange=e=>{this.draft(x.entity_id,"expose",e.target.checked);this.renderList();};
    for(const [id,field] of [["google-name","name"],["google-room","room"],["google-aliases","aliases"]]) {
      el.querySelector("#"+id).oninput=e=>{
        const value=field==="aliases"?e.target.value.split("\n").map(v=>v.trim()).filter(Boolean):e.target.value;
        this.draft(x.entity_id,field,value || null);
      };
      el.querySelector("#"+id).onchange=()=>this.renderList();
    }
  }
  renderBar() {
    const el=this.shadowRoot.querySelector("#bar");if(!el)return;
    const count=Object.keys(this.drafts).length;
    el.innerHTML=count?`<div class="savebar"><span class="pending-icon">${icon("pencil-outline",18)}</span><div><strong>${count} device${count===1?"":"s"} edited</strong><small>${this.external?"Settings changed elsewhere. Refresh before applying.":"Ready when you are. No restart needed."}</small></div><button id="discard" ${this.busy?"disabled":""}>Discard</button><button class="primary" id="review" ${this.busy?"disabled":""}>${this.busy?"Applying…":"Review changes"} ${icon("arrow-right",17)}</button></div>`:"";
    el.querySelector("#discard")?.addEventListener("click",()=>{this.drafts={};this.load();});
    el.querySelector("#review")?.addEventListener("click",()=>this.review());
  }
  dialog(title,body,buttons=[]) {
    const root=this.shadowRoot.querySelector("#modal");
    this.modalFocus=this.shadowRoot.activeElement;
    root.innerHTML=`<dialog aria-labelledby="dialog-title"><div class="modal-head"><h2 id="dialog-title">${esc(title)}</h2><button class="icon" data-close aria-label="Close dialog">${icon("close")}</button></div><div class="modal-body">${body}</div><div class="modal-actions">${buttons.map((b,i)=>`<button data-action="${i}" class="${b.primary?"primary":""}">${esc(b.label)}</button>`).join("")}</div></dialog>`;
    const dialog=root.querySelector("dialog");
    const close=()=>{dialog.close();root.innerHTML="";this.modalFocus?.focus();};
    root.querySelector("[data-close]").onclick=close;
    dialog.addEventListener("cancel",()=>{setTimeout(()=>{root.innerHTML="";this.modalFocus?.focus();},0);});
    buttons.forEach((b,i)=>root.querySelector(`[data-action="${i}"]`).onclick=()=>b.action(close));
    dialog.showModal();return dialog;
  }
  async review(backup=null) {
    try {
      const changes=structuredClone(this.drafts), base=this.data.revision;
      const result=await this.api("preview",{revision:base,changes,...(backup?{backup}:{})});
      if(!result.changes.length){this.toast("Everything is already up to date.");return;}
      const body=`<p class="review-intro">${backup?"Restore this snapshot":"Apply these changes"} to your existing Google connection. A recovery snapshot is saved automatically.</p><div class="changes">${result.changes.map(change=>{
        const item=this.data.items.find(x=>x.entity_id===change.entity_id);
        const fields=[...new Set([...Object.keys(change.before),...Object.keys(change.after)])].filter(k=>JSON.stringify(change.before[k])!==JSON.stringify(change.after[k]));
        const value=(obj,key)=>key==="expose"?(obj[key]?"Shared":"Not shared"):Array.isArray(obj[key])?obj[key].join(", "):obj[key]||"Default";
        return `<div class="change"><strong>${esc(item?.name||change.entity_id)}</strong>${fields.map(k=>`<div><span>${esc(k==="expose"?"Sharing":k)}</span><del>${esc(value(change.before,k))}</del><b>→</b><ins>${esc(value(change.after,k))}</ins></div>`).join("")}</div>`;
      }).join("")}</div><div class="live-note">${icon("lightning-bolt-outline",18)} Apply live, save for future restarts, and ask Google to sync.</div>`;
      this.dialog("A quick look before applying",body,[{label:"Keep editing",action:close=>close()},{label:"Apply & sync",primary:true,action:async close=>{
        close();this.busy=true;this.shadowRoot.querySelector(".workspace").inert=true;this.renderBar();
        try {const result=await this.api("apply",{revision:base,changes,...(backup?{backup}:{})});this.drafts={};await this.load();this.toast(result.sync?.ok?"Saved live. Google sync requested.":result.sync?.message||"Saved live.");}
        catch(e){this.toast(e.message||String(e),true);}finally{this.busy=false;this.shadowRoot.querySelector(".workspace").inert=false;this.renderBar();}
      }}]);
    } catch(e){this.toast(e.message||String(e),true);}
  }
  async history() {
    try {
      const items=await this.api("history");
      const dialog=this.dialog("Recovery snapshots",`<p>A snapshot is saved before every change. Restore previews the exact differences first.</p>${items.length?items.map(x=>`<button class="history-row" data-backup="${esc(x.id)}"><span>${esc(x.id.slice(0,8).replace(/(\d{4})(\d{2})(\d{2})/,"$1-$2-$3"))} · ${esc(x.id.slice(9,15).replace(/(\d{2})(\d{2})(\d{2})/,"$1:$2:$3"))} UTC<small>${x.entities} saved entries</small></span>${icon("restore",20)}</button>`).join(""):"<div class='empty'>Your first snapshot appears after applying a change.</div>"}`);
      dialog.querySelectorAll("[data-backup]").forEach(button=>button.onclick=()=>{dialog.close();this.review(button.dataset.backup);});
    } catch(e){this.toast(e.message||String(e),true);}
  }
  async refresh() {
    if(Object.keys(this.drafts).length){this.dialog("Refresh your devices?","<p>Refreshing discards your unapplied edits.</p>",[{label:"Keep editing",action:close=>close()},{label:"Discard & refresh",primary:true,action:close=>{close();this.drafts={};this.load();}}]);}
    else await this.load();
  }
  async runSync() {
    if(this.busy)return;this.busy=true;
    const button=this.shadowRoot.querySelector("#sync");button.disabled=true;
    try {const result=await this.api("sync");this.data.last_sync=result;this.toast(result.message,!result.ok);if(!Object.keys(this.drafts).length)await this.load();}
    catch(e){this.toast(e.message||String(e),true);}finally{this.busy=false;button.disabled=false;}
  }
  toast(message,error=false) {
    const el=this.shadowRoot.querySelector("#toast");if(!el)return;
    el.innerHTML=`<div class="toast ${error?"failure":""}" role="${error?"alert":"status"}">${esc(message)}</div>`;
    clearTimeout(this.toastTimer);this.toastTimer=setTimeout(()=>{el.innerHTML="";},error?12000:6000);
  }
}

const styles=`
:host{display:block;--ink:var(--primary-text-color,#20322e);--muted:var(--secondary-text-color,#74817b);--surface:var(--card-background-color,#fff);--bg:var(--primary-background-color,#f5f7f4);--line:var(--divider-color,#e3e9e3);--accent:#23846a;--wash:color-mix(in srgb,var(--accent) 10%,var(--surface));color:var(--ink);font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);min-height:100vh}
:host([dark]){--accent:#65c6a6}:host([dark]) .primary,:host([dark]) .mark{background:#23846a;border-color:#23846a}
.brand-logo{display:block;flex:none;width:44px;height:44px}
*{box-sizing:border-box}button,input,textarea,select{font:inherit}button{cursor:pointer;border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:10px;padding:9px 14px;display:inline-flex;align-items:center;justify-content:center;gap:7px;transition:background .15s}button:hover{background:var(--wash)}button:disabled{opacity:.55;cursor:wait}button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #66bda4;outline-offset:3px}.icon{padding:8px;border:none;background:transparent}.primary{background:var(--accent);border-color:var(--accent);color:white;font-weight:650}.primary:hover{background:#1a725b}header{height:78px;padding:0 5%;display:flex;align-items:center;justify-content:space-between;background:var(--surface);border-bottom:1px solid var(--line)}.brand{display:flex;align-items:center;gap:12px;font-size:19px;font-weight:750;letter-spacing:-.5px}.brand small{display:block;font-size:9px;letter-spacing:1.9px;color:var(--muted);font-weight:650;margin-top:1px}.mark{display:grid;place-items:center;background:var(--accent);color:white;border-radius:13px;width:42px;height:42px}.header-actions{display:flex;gap:8px}.header-actions #menu{display:none}main{max-width:1390px;margin:auto;padding:44px 5% 110px}.hero{display:flex;align-items:center;justify-content:space-between;gap:24px;margin-bottom:32px}.eyebrow{font-size:10px;font-weight:750;letter-spacing:2px;color:var(--accent);margin-bottom:10px}h1{font-size:clamp(28px,3.1vw,42px);font-weight:650;letter-spacing:-1.5px;line-height:1.2;margin:0 0 12px}.hero p{margin:0;color:var(--muted);font-size:15px}.connection{display:grid;grid-template-columns:8px auto;column-gap:8px;white-space:nowrap;font-size:12px;font-weight:600}.connection i{border-radius:50%;width:7px;height:7px;background:#2aab7e;align-self:center}.connection span{grid-column:2;color:var(--muted);font-size:11px;font-weight:400;margin-top:4px}.overview{display:flex;align-items:center;gap:0;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:22px 24px;margin-bottom:26px}.overview>div{display:flex;flex-direction:column;flex:1;padding-left:26px;border-left:1px solid var(--line)}.overview>div:first-child{padding-left:0;border:0}.stat{font-size:27px;line-height:1.2;letter-spacing:-1px;font-weight:650}.overview>div>span+span{color:var(--muted);font-size:11px;margin-top:5px}.sync{font-size:12px}.sync-result{display:flex;align-items:center;gap:7px;font-size:12px;color:var(--accent);margin:-12px 0 18px}.warning{color:#bc822f}.workspace{display:grid;grid-template-columns:minmax(0,1fr) 318px;gap:24px;align-items:start}.collection{min-width:0}.toolbar{display:flex;gap:12px}.search{display:flex;align-items:center;gap:9px;flex:1;min-width:0;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:0 12px;color:var(--muted)}input,textarea,select{border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--ink);padding:11px 12px;min-width:0}.search input{border:0;background:transparent;width:100%;padding:11px 0;outline-offset:0}.toolbar select{max-width:155px;font-size:12px}.filters{display:flex;gap:5px;border-bottom:1px solid var(--line);margin-top:19px;padding-bottom:12px;overflow:auto}.filters button{border:0;background:transparent;color:var(--muted);font-size:12px;white-space:nowrap;padding:7px 12px}.filters .active{color:var(--accent);background:var(--wash);font-weight:650}.list-caption{display:flex;align-items:center;justify-content:space-between;color:var(--muted);font-size:11px;margin:9px 0}.list-caption button{background:transparent;border:0;font-size:11px;padding:5px}.bulk{display:flex;align-items:center;gap:8px;margin:12px 0;background:var(--wash);border-radius:9px;padding:9px 12px;font-size:12px}.bulk strong{margin-right:auto}.bulk button{font-size:11px;padding:5px 9px}#list h2{display:flex;gap:9px;align-items:center;font-size:12px;font-weight:650;margin:23px 0 10px}#list h2:first-child{margin-top:12px}#list h2 span{color:var(--muted);font-size:10px;font-weight:400}.row{display:flex;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:9px 15px 9px 12px;margin-bottom:7px;gap:11px;min-height:70px}.row.chosen{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}.row.edited{border-left:3px solid var(--accent)}.select-row{accent-color:var(--accent);width:14px;height:14px;margin:0;flex:none}.device{display:flex;align-items:center;gap:12px;padding:2px 0;border:0;min-width:0;text-align:left;flex:1;background:transparent}.device:hover{background:transparent}.device-icon{height:39px;width:39px;flex:none;display:grid;place-items:center;border-radius:10px;background:var(--bg);color:var(--muted)}.device-icon.on{background:var(--wash);color:var(--accent)}.device-copy{min-width:0;flex:1}.device-copy strong{display:block;font-size:13px;font-weight:600;white-space:nowrap;text-overflow:ellipsis;overflow:hidden}.device-copy small{display:flex;align-items:center;gap:8px;font-size:10px;color:var(--muted);text-transform:capitalize;margin-top:4px}.device>ha-icon{color:var(--muted);opacity:.55}.offline{font-size:10px;color:#bc822f}.draft-dot{color:var(--accent);font-size:10px}.toggle{border:0;background:color-mix(in srgb,var(--muted) 30%,var(--surface));width:36px;height:21px;border-radius:20px;padding:3px;flex:none;justify-content:flex-start}.toggle span{width:15px;height:15px;border-radius:50%;background:white;box-shadow:0 1px 3px #0002}.toggle.on{background:var(--accent)}.toggle.on span{transform:translateX(15px)}aside{background:var(--surface);border:1px solid var(--line);border-radius:16px;position:sticky;top:24px;overflow:hidden}.detail-empty{padding:40px 26px;text-align:center}.detail-empty>span{display:grid;place-items:center;background:var(--wash);color:var(--accent);width:66px;height:66px;border-radius:22px;margin:0 auto 20px}.detail-empty h3{font-size:20px;font-weight:600;letter-spacing:-.5px;margin:0 0 12px}.detail-empty p{font-size:12px;color:var(--muted);line-height:1.8}.live-note{display:flex;gap:9px;align-items:center;text-align:left;padding:15px;border-radius:10px;background:var(--wash);font-size:11px;color:var(--accent);line-height:1.6;margin-top:25px}.live-note ha-icon{flex:none}.detail-head{display:flex;align-items:center;justify-content:space-between;padding:13px 18px;border-bottom:1px solid var(--line);font-size:9px;letter-spacing:1.5px;color:var(--muted);font-weight:650}.detail-title{padding:23px 22px 18px}.big-icon{display:grid;place-items:center;color:var(--accent);background:var(--wash);width:54px;height:54px;border-radius:16px}.detail-title h2{font-size:19px;font-weight:600;line-height:1.35;letter-spacing:-.5px;margin:14px 0 6px}.status{font-size:10px;color:var(--accent)}.status.offline{color:#bc822f}.detail-body{padding:0 22px 22px}.detail-body label{display:block;font-weight:600;font-size:11px;margin-top:22px;margin-bottom:8px}.detail-body input:not([type=checkbox]),.detail-body textarea{width:100%;font-size:12px}.detail-body textarea{resize:vertical}.detail-body .share-field{display:flex;align-items:center;justify-content:space-between;font-size:12px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:17px 0;margin:0}.share-field input{accent-color:var(--accent);width:17px;height:17px}.hint{font-size:10px;line-height:1.65;color:var(--muted);margin:7px 0 0}.retained{color:#bc822f}details{font-size:10px;color:var(--muted);margin-top:25px;border-top:1px solid var(--line);padding-top:16px}summary{cursor:pointer}code{display:block;font-size:10px;word-break:break-all;margin-top:12px}footer{display:flex;justify-content:space-between;color:var(--muted);font-size:10px;border-top:1px solid var(--line);padding-top:19px;margin-top:42px;gap:15px}.savebar{position:fixed;z-index:5;bottom:24px;left:50%;transform:translateX(-50%);background:var(--surface);border:1px solid var(--line);border-radius:15px;box-shadow:0 8px 40px #0002;padding:13px 16px;display:flex;align-items:center;gap:15px;min-width:550px}.pending-icon{color:var(--accent);display:grid;place-items:center;width:34px;height:34px;background:var(--wash);border-radius:10px}.savebar strong{font-size:12px;display:block}.savebar small{font-size:10px;color:var(--muted);display:block}.savebar>div{flex:1}.savebar button{font-size:12px}.toast{position:fixed;z-index:20;bottom:105px;left:50%;transform:translateX(-50%);max-width:90%;padding:13px 22px;border-radius:12px;background:#203d33;color:white;box-shadow:0 8px 30px #0002;font-size:12px}.toast.failure{background:#893c30}.empty{padding:55px 20px;text-align:center;color:var(--muted);font-size:13px}.empty h3{color:var(--ink);font-size:16px;margin-bottom:5px}.empty p{font-size:12px}.notice{padding:16px;margin-bottom:20px;border:1px solid #bc822f;border-radius:12px;font-size:13px}.notice button{margin-left:10px}dialog{border:1px solid var(--line);border-radius:18px;background:var(--surface);color:var(--ink);padding:0;width:min(640px,calc(100vw - 30px));max-height:85vh;box-shadow:0 24px 100px #0004}dialog::backdrop{background:#0e211b77;backdrop-filter:blur(3px)}.modal-head{display:flex;align-items:center;justify-content:space-between;padding:20px 24px;border-bottom:1px solid var(--line)}.modal-head h2{font-size:18px;letter-spacing:-.4px;margin:0;font-weight:600}.modal-body{padding:20px 24px;overflow:auto;max-height:60vh}.modal-body>p{font-size:12px;color:var(--muted);margin-top:0}.modal-actions{display:flex;justify-content:flex-end;gap:10px;padding:16px 24px;border-top:1px solid var(--line)}.change{border:1px solid var(--line);padding:13px;border-radius:10px;margin-top:10px;font-size:11px}.change strong{display:block;margin-bottom:9px;font-size:12px}.change>div{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;padding:3px 0}.change>div>span{width:48px;text-transform:capitalize;color:var(--muted)}.change del{color:var(--muted);text-decoration:none}.change ins{color:var(--accent);text-decoration:none}.change b{color:var(--muted);font-weight:400}.history-row{display:flex;justify-content:space-between;width:100%;text-align:left;margin:9px 0;font-size:12px;padding:13px}.history-row small{display:block;color:var(--muted);font-size:10px;margin-top:4px}
@media(min-width:1600px){main{padding-left:40px;padding-right:40px}}@media(max-width:1000px){.workspace{grid-template-columns:minmax(0,1fr) 285px;gap:16px}main{padding:32px 24px 110px}.connection{display:none}.overview{padding:19px}.overview>div{padding-left:15px}.overview .sync{padding:8px}.sync span{display:none}}@media(max-width:760px){header{height:65px;padding:0 20px}.header-actions #menu{display:inline-flex}.header-actions #history span{display:none}.header-actions #history{border:none;padding:8px}.brand{font-size:16px}.mark{width:36px;height:36px}.brand small{font-size:8px}main{padding:28px 16px 120px}.hero{margin-bottom:24px}.hero p{font-size:12px;max-width:260px}.eyebrow{font-size:9px}.overview{padding:18px 15px;flex-wrap:wrap;gap:18px}.overview>div{padding-left:15px;flex:1}.overview>div:first-child{padding-left:0}.stat{font-size:23px}.overview>div>span+span{font-size:9px}.overview .sync{width:100%;font-size:11px;padding:6px}.workspace{display:block}aside:not(.open){display:none}aside.open{position:fixed;z-index:10;top:auto;bottom:0;left:0;right:0;max-height:87vh;overflow:auto;border-radius:20px 20px 0 0;box-shadow:0 -15px 100px #0005;padding-bottom:30px}.detail-title{display:grid;grid-template-columns:54px auto;column-gap:15px;align-items:center}.detail-title h2{margin:0}.detail-title .big-icon{grid-row:span 2}.detail-title .status{align-self:start}.detail-body{padding:0 22px 22px}.toolbar{gap:8px}.toolbar select{max-width:110px;font-size:11px;padding:9px}.search{padding:0 9px}.search input{font-size:11px}.filters button{font-size:11px;padding:7px 10px}.row{padding:9px 12px;gap:8px}.device{gap:9px}.device-copy strong{font-size:12px}.device-icon{height:34px;width:34px}.device>ha-icon{display:none}.savebar{bottom:12px;min-width:0;width:calc(100% - 24px);padding:11px 12px;gap:9px}.savebar small{max-width:150px;font-size:9px}.savebar button{font-size:10px;padding:9px}.pending-icon{display:none}footer{font-size:9px;flex-direction:column;gap:6px}.modal-head,.modal-body,.modal-actions{padding:16px}.modal-head h2{font-size:16px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}
`;
if(!customElements.get("home-share-panel"))customElements.define("home-share-panel",HomeSharePanel);
