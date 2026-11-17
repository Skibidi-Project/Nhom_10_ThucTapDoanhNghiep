"use strict";
const $ = id => document.getElementById(id);
let readings = [], room = null, busy = false;
function notice(text,error=false){$("notice").textContent=text;$("notice").className=error?"error":"";$("notice").hidden=false;}
async function api(path,options={}){
    const response=await fetch(`/api${path}`,{...options,headers:{Authorization:`Bearer ${sessionStorage.getItem("us05_access_token")||""}`,...(options.body?{"Content-Type":"application/json"}:{})}});
    const data=await response.json().catch(()=>null);
    if(!response.ok){
        if(response.status===401){sessionStorage.removeItem("us05_access_token");$("workspace").hidden=true;throw new Error("Phiên không hợp lệ. Vui lòng đăng nhập lại.");}
        if(response.status===403)throw new Error("Bạn không có quyền quản lý chỉ số của phòng này. Phiên đăng nhập vẫn được giữ.");
        const detail=typeof data?.detail==="string"?data.detail:Array.isArray(data?.detail)?data.detail.map(x=>x.msg).join("; "):"Yêu cầu thất bại.";
        throw new Error(`HTTP ${response.status}: ${detail}`);
    }
    return data;
}
function latest(){return readings.filter(r=>r.utility_type===$("kind").value).sort((a,b)=>b.period.localeCompare(a.period))[0];}
function preview(){
    const a=$("previous").value,b=$("current").value;
    $("usage").textContent=a!==""&&b!==""&&Number(b)>=Number(a)?`${Number(b)-Number(a)} ${$("kind").value==="water"?"m³":"kWh"}`:"—";
}
function suggest(){
    const last=latest();
    $("latest").textContent=last?`Kỳ gần nhất ${last.period} · Chỉ số cuối: ${last.current_reading}`:"Chưa có kỳ trước. Nhập chỉ số ban đầu.";
    $("previous").value=last?last.current_reading:0;
    if(last){const [y,m]=last.period.split("-").map(Number);$("period").value=`${m===12?y+1:y}-${String(m===12?1:m+1).padStart(2,"0")}`;}
    else {const d=new Date();$("period").value=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;}
    $("current").value="";preview();
}
function render(){
    $("rows").replaceChildren();
    const list=readings.filter(r=>["electricity","water"].includes(r.utility_type)).sort((a,b)=>b.period.localeCompare(a.period)||a.utility_type.localeCompare(b.utility_type));
    for(const r of list){
        const row=document.createElement("tr");
        for(const value of [r.period,r.utility_type==="water"?"Nước":"Điện",r.previous_reading,r.current_reading,`${r.current_reading-r.previous_reading} ${r.utility_type==="water"?"m³":"kWh"}`]){const cell=document.createElement("td");cell.textContent=value;row.append(cell);}
        $("rows").append(row);
    }
    $("count").textContent=`${list.length} bản ghi`;$("roomLabel").textContent=`Phòng #${room} · Dữ liệu mới nhất từ hệ thống`;
    $("empty").hidden=list.length!==0;$("workspace").hidden=false;suggest();
}
async function load(id){if(!Number.isSafeInteger(id)||id<1)throw new Error("Mã phòng phải là số nguyên dương.");const data=await api(`/rooms/${id}/readings`);room=id;readings=data;render();}
async function action(fn){if(busy)return;busy=true;document.querySelectorAll("button").forEach(b=>b.disabled=true);$("loading").hidden=false;try{await fn();}catch(e){notice(e instanceof TypeError?"Không kết nối được máy chủ.":e.message,true);}finally{busy=false;$("loading").hidden=true;document.querySelectorAll("button").forEach(b=>b.disabled=false);}}
$("roomForm").onsubmit=e=>{e.preventDefault();action(async()=>{$("workspace").hidden=true;await load(Number($("roomId").value));$("notice").hidden=true;});};
$("kind").onchange=suggest;
$("previous").oninput=preview;$("current").oninput=preview;
$("readingForm").onsubmit=e=>{e.preventDefault();action(async()=>{
    const payload={utility_type:$("kind").value,period:$("period").value,previous_reading:Number($("previous").value),current_reading:Number($("current").value)};
    // The API is authoritative, including duplicate/backdated periods and continuity.
    await api(`/rooms/${room}/readings`,{method:"POST",body:JSON.stringify(payload)});
    await load(room);notice("Đã lưu chỉ số thành công.");
});};
$("roomId").value=new URLSearchParams(location.search).get("room_id")||"1";
action(async()=>{
    if(!sessionStorage.getItem("us05_access_token")){notice("Vui lòng đăng nhập bằng tài khoản Chủ trọ hoặc Quản lý.",true);return;}
    const user=await api("/users/me");$("account").textContent=`${user.full_name} · ${user.role}`;await load(Number($("roomId").value));
});
