/* Build: "Building a Claude Code Workspace" — 25-slide bootcamp deck, ~55 min — Hinglish */
const G = "/opt/homebrew/lib/node_modules/";
const pptxgen = require(G + "pptxgenjs");
const React = require(G + "react");
const ReactDOMServer = require(G + "react-dom/server");
const sharp = require(G + "sharp");
const fa = require(G + "react-icons/fa6");

const DARK="151622", CODEBG="1E1F2E", CLAY="D97757", CLAYDK="B85C3E",
      INK="23262F", SLATE="5C6472", LIGHT="FFFFFF", CARD="F4F5F8",
      WARM="FBF1EA", BORDER="E4E7ED", ICE="AEB6CC", WHITE="FFFFFF",
      GREENBADGE="3F8F5B", RED="C2503F";
const C_FG="C6CEF0", C_GUIDE="5B6488", C_COMMENT="6B7494",
      C_KEY="7AA2F7", C_GREEN="9ECE6A", C_PURP="BB9AF7";

const SW=13.333, SH=7.5, MX=0.65;

function svg(C,color,s){ return ReactDOMServer.renderToStaticMarkup(React.createElement(C,{color,size:String(s)})); }
async function png(C,color,s=256){ return "image/png;base64,"+(await sharp(Buffer.from(svg(C,color,s))).png().toBuffer()).toString("base64"); }
const I={};
async function reg(k,C,color){ I[k]=await png(C,color); }
const shadow=()=>({type:"outer",color:"000000",blur:7,offset:3,angle:90,opacity:0.13});

(async()=>{
  await reg("list",fa.FaListCheck,"#FFFFFF");
  await reg("layer",fa.FaLayerGroup,"#FFFFFF");
  await reg("cube",fa.FaCubes,"#FFFFFF");
  await reg("tree",fa.FaFolderTree,"#FFFFFF");
  await reg("brain",fa.FaBrain,"#FFFFFF");
  await reg("gear",fa.FaGears,"#FFFFFF");
  await reg("robot",fa.FaRobot,"#FFFFFF");
  await reg("puzzle",fa.FaPuzzlePiece,"#FFFFFF");
  await reg("plug",fa.FaPlug,"#FFFFFF");
  await reg("scale",fa.FaScaleBalanced,"#FFFFFF");
  await reg("play",fa.FaPlay,"#FFFFFF");
  await reg("hand",fa.FaHandPointer,"#FFFFFF");
  await reg("check",fa.FaCircleCheck,"#FFFFFF");
  await reg("term",fa.FaTerminal,"#FFFFFF");
  await reg("lock",fa.FaShieldHalved,"#FFFFFF");
  await reg("book",fa.FaBookOpen,"#FFFFFF");
  await reg("bolt",fa.FaBolt,"#FFFFFF");
  await reg("eye",fa.FaEye,"#FFFFFF");
  await reg("code",fa.FaCode,"#FFFFFF");
  await reg("c_check",fa.FaCircleCheck,"#3F8F5B");
  await reg("c_x",fa.FaCircleXmark,"#C2503F");
  await reg("c_arrow",fa.FaAngleRight,"#D97757");
  await reg("c_brain",fa.FaBrain,"#D97757");
  await reg("c_robot",fa.FaRobot,"#D97757");
  await reg("c_puzzle",fa.FaPuzzlePiece,"#D97757");
  await reg("c_plug",fa.FaPlug,"#D97757");
  await reg("c_tree",fa.FaFolderTree,"#D97757");
  await reg("c_term",fa.FaTerminal,"#D97757");
  await reg("c_layer",fa.FaLayerGroup,"#D97757");
  await reg("c_code",fa.FaCode,"#D97757");
  await reg("c_eye",fa.FaEye,"#D97757");
  await reg("motif",fa.FaFolderTree,"#D97757");

  const p=new pptxgen();
  p.defineLayout({name:"W",width:SW,height:SH});
  p.layout="W";
  p.author="Friday Bootcamp";
  p.title="Building a Claude Code Workspace — Bootcamp";

  function circle(s,x,y,d,img,fill=CLAY){
    s.addShape(p.shapes.OVAL,{x,y,w:d,h:d,fill:{color:fill}});
    const pad=d*0.27;
    s.addImage({data:img,x:x+pad,y:y+pad,w:d-2*pad,h:d-2*pad});
  }
  function header(s,iconKey,kicker,title){
    circle(s,MX,0.5,0.78,I[iconKey],CLAY);
    s.addText(kicker.toUpperCase(),{x:1.62,y:0.5,w:10.8,h:0.3,fontFace:"Arial",fontSize:12.5,bold:true,color:CLAY,charSpacing:2,valign:"middle",margin:0});
    s.addText(title,{x:1.6,y:0.8,w:11.2,h:0.55,fontFace:"Arial",fontSize:27,bold:true,color:INK,valign:"middle",margin:0});
  }
  function footer(s,n){
    s.addText("Building a Claude Code Workspace",{x:MX,y:7.08,w:7,h:0.3,fontFace:"Arial",fontSize:8.5,color:"B9C0CC",margin:0});
    s.addText(String(n),{x:SW-1.1,y:7.08,w:0.45,h:0.3,fontFace:"Arial",fontSize:9,bold:true,color:CLAY,align:"right",margin:0});
    if(typeof NOTES!=="undefined"&&NOTES[n]) s.addNotes(NOTES[n]);
  }
  function card(s,x,y,w,h,fill=CARD,sh=true){
    s.addShape(p.shapes.ROUNDED_RECTANGLE,{x,y,w,h,fill:{color:fill},rectRadius:0.09,...(sh?{shadow:shadow()}:{})});
  }
  function lines2runs(lines){
    const runs=[];
    lines.forEach(line=>{
      if(line.length===0){runs.push({text:" ",options:{breakLine:true}});return;}
      line.forEach((seg,i)=>runs.push({text:seg.t,options:{color:seg.c||C_FG,bold:!!seg.b,breakLine:i===line.length-1}}));
    });
    return runs;
  }
  function codeBlock(s,x,y,w,h,lines,fs=12.5){
    s.addShape(p.shapes.ROUNDED_RECTANGLE,{x,y,w,h,fill:{color:CODEBG},rectRadius:0.07,shadow:shadow()});
    s.addText(lines2runs(lines),{x:x+0.22,y:y+0.16,w:w-0.4,h:h-0.32,fontFace:"Courier New",fontSize:fs,valign:"top",lineSpacingMultiple:1.06,margin:0});
  }
  function darkBar(s,runs,y=6.0,h=0.7){
    s.addText(runs,{x:MX,y,w:12.05,h,fontFace:"Arial",fontSize:13,align:"center",valign:"middle",fill:{color:DARK},margin:0.14,lineSpacingMultiple:1.1});
  }
  const T=(g)=>({t:g,c:C_GUIDE}), F=(n)=>({t:n,c:"E0A878",b:true}), f=(n)=>({t:n,c:C_FG}),
        cm=(n)=>({t:n,c:C_COMMENT}), gr=(n)=>({t:n,c:C_GREEN,b:true});
  const yk=(t)=>({t,c:C_KEY,b:true}), yv=(t)=>({t,c:C_FG}), yc=(t)=>({t,c:C_COMMENT}),
        dl=(t)=>({t,c:C_GUIDE}), md=(t)=>({t,c:C_PURP,b:true}), gln=(t)=>({t,c:C_GREEN});

  const NOTES={
1:`Open with energy: "Aaj hum Claude Code ko ek project ka permanent teammate banate hain." 55 min: concept + live demo + hands-on. Reassure: no API key needed.`,
2:`Read each topic name + one phrase. Bolo: "Last 5 min tumhara — haath se karo." Point at bottom bar — "Yeh 4 cheezein leke jaana hai."`,
3:`Yeh aha slide hai. Teen points slowly bolo. "Tumhara code waise hi rehta hai — kuch delete nahi hua." .claude/ ek thin layer hai jo git mein jaati hai. Clone karo — instantly productive.`,
4:`Bottom to top point karo: code → settings → workspace. Analogy: ".claude/ = nayi job pe onboarding handbook + specialists ki team — git mein checked in."`,
5:`Simple app, complex workspace — that is the lesson. App ke bina API key ke bhi chalti hai — stage pe fail nahi hogi.`,
6:`Har file pe ~20 sec. Main rule stress karo: .claude/ IS committed (green). .env NEVER committed (red).`,
7:`"Claude yeh file har session ke SHURU mein padh leta hai — automatically." 200 lines se chhota rakho. Long procedures → Skills mein.`,
8:`Allow list = Claude bina pooche yeh commands run kar sakta hai. Deny list = Claude kabhi .env nahi padh sakta — chahe koi keh de.`,
9:`Two columns: commit karo vs kabhi mat karo. Golden rule: .env.example mein sirf placeholder — real key kabhi nahi.`,
10:`"Agent = alag Claude — apna context, apne tools, apna model." description field = trigger. tools list = sandbox.`,
11:`Model selection = cost decision. Security → Opus (miss nahi kar sakte CRITICAL). Perf → Sonnet. Style → Haiku. Total per PR: ~$0.10.`,
12:`Skill = ek folder with SKILL.md. Package once, use forever. description = trigger. Koi install restart nahi — folder daalo, live.`,
13:`Progressive disclosure = context bloat nahi hota. Level 1: metadata only. Level 2: body on trigger. Level 3: reference on demand.`,
14:`Commands = single .md file, /command-name se run. Skill vs Command: Skill = multi-step, Command = quick one-shot.`,
15:`MCP = Claude ko bahar connect karo. DB, GitHub, web — sab ek protocol. .mcp.json committed = team share karta hai same tools.`,
16:`Agent = isolation chahiye. Skill = procedure chahiye. MCP = bahar jaana hai. Compose karte hain — ek dusre ke saath.`,
17:`Yeh aha moment #2. Kuch manually configure nahi kiya. CLAUDE.md loaded → agents scanned → user bola → match hua → body loaded → run. System, not just config.`,
18:`Do commands, 30 seconds. "Maine CLAUDE.md set ki thi — CLAUDE.md aur settings.json ne sab karaya." Never debug live > 30 sec.`,
19:`Agents ko kaam karte dikhao. "Bina workspace ke PR review mein kitne bugs milte?" Then agents sab pakad lete hain — parallel, automatic.`,
20:`5 min hands-on. 3 steps. Give 3 min silent time — walk around, help individually. Phir screen pe dikhao.`,
21:`Workspace se GitHub tak ka poora journey. Step 1-8 workspace, Step 9-10 git. "Clone karo — instantly productive."`,
22:`"5 cheezein — inhe yaad rakhna. Baki sab bhul jaao." Poochho: "Sabse surprising kya laga?"`,
23:`project3 = production-grade workspace. LangGraph supervisor, 3 agents parallel, webhook. Clone karo — immediately productive.`,
24:`GSD system = Meta-Prompting + Context Engineering + Spec-Driven Dev. Workspace teeno implement karta hai automatically.`,
25:`"Shukriya. Sab kuch repo mein hai." Open Q&A. 3 tough questions ke jawab ready rakhna.`,
  };

  // =========================================================
  // 1 — TITLE
  // =========================================================
  let s=p.addSlide(); s.background={color:DARK};
  s.addImage({data:I.motif,x:8.8,y:1.0,w:5.2,h:5.2,transparency:90});
  s.addText("HANDS-ON BOOTCAMP  ·  55 MIN",{x:MX,y:1.5,w:10,h:0.35,fontFace:"Arial",fontSize:14,bold:true,color:CLAY,charSpacing:3,margin:0});
  s.addText("Building a",{x:MX-0.03,y:1.95,w:11.5,h:0.95,fontFace:"Arial",fontSize:50,bold:true,color:WHITE,margin:0});
  s.addText("Claude Code Workspace",{x:MX-0.03,y:2.8,w:12.3,h:1.0,fontFace:"Arial",fontSize:50,bold:true,color:CLAY,margin:0});
  s.addText("Ek real project ko structure karo — Agents + Skills + MCP —\naur dekho Claude apne aap ek smart teammate ban jaata hai.",{x:MX,y:4.0,w:9.4,h:0.9,fontFace:"Arial",fontSize:16,color:ICE,lineSpacingMultiple:1.25,margin:0});
  s.addShape(p.shapes.LINE,{x:MX,y:5.3,w:2.0,h:0,line:{color:CLAY,width:2}});
  s.addText([{text:"Friday Bootcamp",options:{bold:true,color:WHITE,breakLine:true}},{text:"Live demo + haath se karo  ·  Demo repos: workspace_demo + project3",options:{color:ICE,fontSize:12}}],{x:MX,y:5.5,w:10,h:0.7,fontFace:"Arial",fontSize:14,margin:0});
  s.addNotes(NOTES[1]);

  // =========================================================
  // 2 — AGENDA
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"list","Aaj ka plan","55 minute mein yeh cover karenge");
  const ag=[
    ["c_layer","Mental Model","code + .claude/ layer kya hota hai"],
    ["c_tree","Folder Map","har file ka kaam kya hai"],
    ["c_brain","CLAUDE.md & Settings","memory + rules + secrets"],
    ["c_robot","Agents","specialist subagents + model selection"],
    ["c_puzzle","Skills","reusable workflows kaise banate hain"],
    ["c_code","Commands","slash commands + auto-flow"],
    ["c_plug","MCP","bahar ke tools connect karo"],
    ["c_eye","Real-world","project3 + GSD system"],
  ];
  {const cw=3.0,ch=1.25,gx=0.22,gy=0.22,x0=MX,y0=1.82;
    ag.forEach((a,i)=>{const c=i%4,r=Math.floor(i/4);
      const x=x0+c*(cw+gx),y=y0+r*(ch+gy);
      card(s,x,y,cw,ch,CARD,true);
      circle(s,x+0.22,y+0.35,0.55,I[a[0].replace("c_","")],CLAY);
      s.addText(a[1],{x:x+0.9,y:y+0.28,w:cw-1.05,h:0.35,fontFace:"Arial",fontSize:13,bold:true,color:INK,margin:0});
      s.addText(a[2],{x:x+0.9,y:y+0.64,w:cw-1.05,h:0.5,fontFace:"Arial",fontSize:10,color:SLATE,margin:0,lineSpacingMultiple:1.1});
    });
  }
  darkBar(s,[{text:"Yeh 4 cheezein leke jaana hai:  ",options:{bold:true,color:WHITE}},{text:"workspace banao · Agent add karo · Skill add karo · kya commit karna hai pata ho.",options:{color:ICE}}],5.8,0.66);
  footer(s,2);

  // =========================================================
  // 3 — WORKSPACE KA MATLAB
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"brain","Sabse pehle","Workspace ka matlab kya hai?");
  const wm=[
    ["1","Tumhara code waise hi rehta hai","backend/, frontend/, src/ — kuch delete nahi hota. Workspace tumhare code ke UPAR ek얇a layer add karta hai, neeche kuch nahi chhedta.","DARK"],
    ["2",".claude/ — ek committed config layer","Agents, Skills, Settings, CLAUDE.md — yeh sab ek folder mein. Git mein committed hoti hai taaki poori team share kare.","CLAY"],
    ["3","Clone karo — Claude ko sab pata hota hai","Naya developer clone karta hai → Claude pehle se project jaanta hai. Koi onboarding nahi, koi re-explaining nahi.","GREENBADGE"],
  ];
  {let y=1.9; wm.forEach((w,i)=>{
    card(s,MX,y,12.05,1.35,i===1?WARM:CARD,true);
    s.addShape(p.shapes.OVAL,{x:MX+0.25,y:y+0.4,w:0.55,h:0.55,fill:{color:i===0?DARK:i===1?CLAY:GREENBADGE}});
    s.addText(w[0],{x:MX+0.25,y:y+0.4,w:0.55,h:0.55,fontFace:"Arial",fontSize:20,bold:true,color:WHITE,align:"center",valign:"middle",margin:0});
    s.addText(w[1],{x:MX+1.05,y:y+0.2,w:10.7,h:0.38,fontFace:"Arial",fontSize:16,bold:true,color:INK,margin:0});
    s.addText(w[2],{x:MX+1.05,y:y+0.62,w:10.7,h:0.6,fontFace:"Arial",fontSize:12.5,color:SLATE,lineSpacingMultiple:1.15,margin:0});
    y+=1.52;
  });}
  darkBar(s,[{text:"Ek line mein:  ",options:{bold:true,color:WHITE}},{text:"Workspace = Code + .claude/ layer.  Ek baar setup karo, hamesha kaam karo, poori team share kare.",options:{color:ICE}}],6.42,0.55);
  footer(s,3);

  // =========================================================
  // 4 — MENTAL MODEL
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"layer","Concept","Workspace ka mental model");
  s.addText([{text:"Tumhara repo nahi badlta.  ",options:{bold:true,color:INK}},{text:"Workspace ek얇a config layer add karta hai code ke upar — jo bhi clone kare, use Claude pehle se project jaanta hua milta hai.",options:{color:SLATE}}],{x:MX,y:1.75,w:6.0,h:1.2,fontFace:"Arial",fontSize:15,lineSpacingMultiple:1.3,valign:"top",margin:0});
  const mm=[["Memory","CLAUDE.md — har session mein Claude yeh padh leta hai","c_brain"],["Capabilities","Agents & Skills — reusable kaam ke units","c_robot"],["Connections",".mcp.json — bahar ke tools se link","c_plug"],["Governance","settings.json — kya allow, kya deny","lock"]];
  {let y=3.05; mm.forEach(m=>{
    circle(s,MX,y,0.6,I[m[2].replace("c_","")],CLAY);
    s.addText(m[0],{x:MX+0.82,y:y-0.02,w:5.2,h:0.3,fontFace:"Arial",fontSize:14,bold:true,color:INK,margin:0});
    s.addText(m[1],{x:MX+0.82,y:y+0.28,w:5.2,h:0.4,fontFace:"Arial",fontSize:11,color:SLATE,margin:0});
    y+=0.9;
  });}
  {const rx=7.35,rw=5.3;
    const layers=[["CLAUDE.md  +  .claude/  +  .mcp.json",WARM,CLAYDK,1.0],["settings.json  ·  permissions  ·  hooks",CARD,INK,1.0],["backend/  ·  frontend/   ( tumhara code )",CODEBG,WHITE,1.5]];
    let y=2.05; layers.forEach(L=>{card(s,rx,y,rw,L[3]-0.16,L[1],true);
      s.addText(L[0],{x:rx+0.3,y,w:rw-0.6,h:L[3]-0.16,fontFace:"Courier New",fontSize:12.5,bold:true,color:L[2],valign:"middle",margin:0});
      y+=L[3];});
    s.addText("workspace layer  ▲",{x:rx,y:1.74,w:rw,h:0.28,fontFace:"Arial",fontSize:10,bold:true,color:CLAY,align:"right",charSpacing:1,margin:0});
  }
  footer(s,4);

  // =========================================================
  // 5 — DEMO PROJECT
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"cube","Demo app","Jis app ke around workspace banayenge");
  s.addText([{text:"App chhoti hai — aur yahi point hai.  ",options:{bold:true,color:INK}},{text:"Workspace uske around wrap hoti hai. API key nahi chahiye — demo mode mein chalti hai, stage pe fail nahi hogi.",options:{color:SLATE}}],{x:MX,y:1.75,w:6.0,h:1.4,fontFace:"Arial",fontSize:15,lineSpacingMultiple:1.3,valign:"top",margin:0});
  const stack=[["Backend","Python · FastAPI · Anthropic SDK","c_term"],["Frontend","plain HTML / CSS / JavaScript","c_tree"],["Workspace layer",".claude/ + CLAUDE.md + .mcp.json","c_layer"]];
  {let y=3.35; stack.forEach(m=>{
    circle(s,MX,y,0.58,I[m[2].replace("c_","")],CLAY);
    s.addText([{text:m[0]+"  ",options:{bold:true,color:INK}},{text:m[1],options:{color:SLATE,fontFace:"Courier New",fontSize:12}}],{x:MX+0.8,y:y+0.05,w:5.3,h:0.4,fontFace:"Arial",fontSize:14,valign:"middle",margin:0});
    y+=0.85;
  });}
  {const rx=7.35,rw=5.3; card(s,rx,1.95,rw,4.3,CARD,true);
    s.addText("Message ka flow kaise hota hai",{x:rx,y:2.15,w:rw,h:0.35,fontFace:"Arial",fontSize:13,bold:true,color:CLAYDK,align:"center",margin:0});
    const steps=[["Browser","frontend/app.js"],["POST /api/chat","backend/main.py"],["Claude API","backend/llm.py"],["Reply → UI","screen pe dikhta hai"]];
    let y=2.75; steps.forEach((st,i)=>{
      s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:rx+0.7,y,w:rw-1.4,h:0.62,fill:{color:i%2?WARM:WHITE},rectRadius:0.06,line:{color:BORDER,width:1}});
      s.addText([{text:st[0]+"   ",options:{bold:true,color:INK}},{text:st[1],options:{color:SLATE,fontFace:"Courier New",fontSize:10}}],{x:rx+0.85,y,w:rw-1.6,h:0.62,fontFace:"Arial",fontSize:12.5,valign:"middle",margin:0});
      if(i<steps.length-1) s.addImage({data:I.c_arrow,x:rx+rw/2-0.16,y:y+0.6,w:0.32,h:0.32,rotate:90});
      y+=0.85;
    });
  }
  footer(s,5);

  // =========================================================
  // 6 — FOLDER MAP
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"tree","Folder map","Workspace — har file ka kaam");
  const tree=[
    [F("workspace_demo/")],
    [T("├── "),F(".claude/"),cm("            # config layer (committed)")],
    [T("│   ├── "),f("settings.json"),cm("    # permissions, env")],
    [T("│   ├── "),F("agents/"),cm("          # subagents (code-reviewer…)")],
    [T("│   ├── "),F("skills/"),cm("          # workflows (add-endpoint…)")],
    [T("│   └── "),F("commands/"),cm("        # slash commands (/ship-check)")],
    [T("├── "),gr("CLAUDE.md"),cm("            # project memory, every session")],
    [T("├── "),f(".mcp.json"),cm("            # external tool connections")],
    [T("├── "),f(".gitignore"),cm("           # .env & *.local bahar rakho")],
    [T("├── "),F("backend/"),cm("             # FastAPI app (Python)")],
    [T("└── "),F("frontend/"),cm("            # HTML / CSS / JS")],
  ];
  codeBlock(s,MX,1.78,7.95,4.5,tree,12.5);
  {const rx=8.85,rw=3.85; let y=1.95;
    const leg=[["✅ Commit karo — share hoga",".claude/, CLAUDE.md, .mcp.json — team ko same setup milega."],["❌ Git se bahar rakho",".env (tumhari key) aur *.local.json (personal overrides)."],["~/.claude/ bhi hota hai","User scope — tumhare saare projects pe laagu."]];
    leg.forEach(l=>{card(s,rx,y,rw,1.4,CARD,true);
      s.addText(l[0],{x:rx+0.26,y:y+0.16,w:rw-0.5,h:0.3,fontFace:"Arial",fontSize:12.5,bold:true,color:CLAYDK,margin:0});
      s.addText(l[1],{x:rx+0.26,y:y+0.5,w:rw-0.5,h:0.8,fontFace:"Arial",fontSize:11,color:SLATE,lineSpacingMultiple:1.12,margin:0});
      y+=1.55;
    });
  }
  footer(s,6);

  // =========================================================
  // 7 — CLAUDE.md
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"brain","Memory","CLAUDE.md — Claude ki yaaddasht");
  codeBlock(s,MX,1.85,6.5,4.3,[
    [({t:"# Workspace Demo — AI Chat",c:C_COMMENT})],
    [],
    [md("## Commands")],
    [yv("- run: `uvicorn backend.main:app`")],
    [],
    [md("## Conventions")],
    [yv("- 4-space indent, type hints")],
    [yv("- secrets in .env, never hardcode")],
    [],
    [md("## Capabilities")],
    [yv("- agents: code-reviewer, api-tester")],
    [yv("- skills: add-endpoint, run-app")],
  ],12.5);
  {const rx=7.5,rw=5.2; let y=1.95;
    const pts=[["Har session mein load hoti hai","Claude session shuru hote hi yeh padh leta hai — automatically."],["Sirf docs nahi","Run commands, conventions, architecture — jo Claude ko hamesha pata hona chahiye."],["Jaldi generate karo","Run /init — Claude repo scan karke pehla draft banata hai."],["Lambi cheez → Skills mein","Procedures CLAUDE.md mein nahi — Skills mein daalo."]];
    pts.forEach(pt=>{circle(s,rx,y,0.5,I.check,CLAY);
      s.addText(pt[0],{x:rx+0.7,y:y-0.04,w:rw-0.7,h:0.3,fontFace:"Arial",fontSize:14,bold:true,color:INK,margin:0});
      s.addText(pt[1],{x:rx+0.7,y:y+0.3,w:rw-0.7,h:0.55,fontFace:"Arial",fontSize:11.5,color:SLATE,lineSpacingMultiple:1.1,margin:0});
      y+=1.08;
    });
  }
  footer(s,7);

  // =========================================================
  // 8 — SETTINGS.JSON
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"gear","Rules","settings.json — Claude ke liye guardrails");
  s.addText("Kya allow hai  ·  Kya deny hai  ·  Env vars  ·  Hooks",{x:MX,y:1.75,w:12.05,h:0.3,fontFace:"Arial",fontSize:13,italic:true,color:SLATE,margin:0});
  codeBlock(s,MX,2.15,6.05,3.2,[
    [yk("\"permissions\""),yv(": {")],
    [yv("  \"allow\": ["),gln("\"Bash(uvicorn:*)\""),yv(",")],
    [yv("             "),gln("\"Bash(pip:*)\""),yv(",")],
    [yv("             "),gln("\"Bash(pytest:*)\""),yv("],")],
    [yv("  \"deny\":  ["),({t:"\"Read(./.env)\"",c:"F7768E"}),yv("]")],
    [yv("},")],
    [yk("\"env\""),yv(": { \"PYTHONUNBUFFERED\": \"1\" }")],
  ],11.5);
  s.addText("Allow: Claude yeh commands bina pooche run kar sakta hai.\nDeny: Claude kabhi bhi .env nahi padh sakta — chahe koi bhi bol de.",{x:MX,y:5.42,w:6.05,h:0.7,fontFace:"Arial",fontSize:11,italic:true,color:SLATE,lineSpacingMultiple:1.2,margin:0});
  {const rx=7.3,rw=5.45; let y=2.15;
    const pts=[["Personal overrides → settings.local.json","Gitignored. Tumhari machine ke tweaks team ko affect nahi karenge."],["User scope → ~/.claude/settings.json","Tumhare SAARE projects pe globally apply hoga."],["Precedence chain","managed  >  local  >  project  >  user"],["Hooks","Tool events pe shell commands run karo (pre-commit, post-edit)."]];
    pts.forEach((pt,i)=>{card(s,rx,y,rw,1.08,i%2===0?CARD:WARM,true);
      s.addText(pt[0],{x:rx+0.26,y:y+0.14,w:rw-0.5,h:0.3,fontFace:"Arial",fontSize:12.5,bold:true,color:CLAYDK,margin:0});
      s.addText(pt[1],{x:rx+0.26,y:y+0.48,w:rw-0.5,h:0.5,fontFace:"Arial",fontSize:11,color:SLATE,lineSpacingMultiple:1.08,margin:0});
      y+=1.18;
    });
  }
  footer(s,8);

  // =========================================================
  // 9 — .GITIGNORE
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"lock","Secrets","Kya commit karo, kya mat karo");
  {const lx=MX,rx=6.95,cw=5.9;
    card(s,lx,1.9,cw,4.3,CARD,true);
    s.addImage({data:I.c_check,x:lx+0.28,y:2.06,w:0.38,h:0.38});
    s.addText("Commit karo — team share karti hai",{x:lx+0.78,y:2.04,w:cw-1.0,h:0.35,fontFace:"Arial",fontSize:14,bold:true,color:GREENBADGE,margin:0});
    const commit=[".claude/  —  agents, skills, settings, commands",".env.example  —  sirf placeholder, real key nahi","CLAUDE.md  —  project memory",".mcp.json  —  team MCP servers"];
    let y=2.55; commit.forEach(t=>{s.addImage({data:I.c_arrow,x:lx+0.3,y:y+0.04,w:0.22,h:0.22});
      s.addText(t,{x:lx+0.65,y:y-0.04,w:cw-0.9,h:0.5,fontFace:"Courier New",fontSize:11.5,color:INK,valign:"top",margin:0});
      y+=0.58;});
    card(s,rx,1.9,cw,4.3,CARD,true);
    s.addImage({data:I.c_x,x:rx+0.28,y:2.06,w:0.38,h:0.38});
    s.addText("Kabhi commit mat karo — secrets!",{x:rx+0.78,y:2.04,w:cw-1.0,h:0.35,fontFace:"Arial",fontSize:14,bold:true,color:RED,margin:0});
    const ignore=[".env  —  real API keys (ANTHROPIC_API_KEY etc.)","*.local.json  —  personal settings overrides","__pycache__/  —  compiled Python bytecode",".venv/  —  virtual environment (100 MB+)"];
    y=2.55; ignore.forEach(t=>{s.addImage({data:I.c_arrow,x:rx+0.3,y:y+0.04,w:0.22,h:0.22});
      s.addText(t,{x:rx+0.65,y:y-0.04,w:cw-0.9,h:0.5,fontFace:"Courier New",fontSize:11.5,color:INK,valign:"top",margin:0});
      y+=0.58;});
  }
  darkBar(s,[{text:"Agar real key commit ho jaaye:  ",options:{bold:true,color:WHITE}},{text:"turant rotate karo (console.anthropic.com pe revoke karo, naya banao), phir git history saaf karo.",options:{color:ICE}}],6.42,0.55);
  footer(s,9);

  // =========================================================
  // 10 — AGENTS
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"robot","Agents","Specialist subagents — alag Claude, alag kaam");
  codeBlock(s,MX,1.85,6.7,4.0,[
    [dl("---"),yc("   .claude/agents/code-reviewer.md")],
    [yk("name:"),yv(" code-reviewer")],
    [yk("description:"),yv(" Reviews diffs for bugs")],
    [yv("  & security. Use after edits.")],
    [yk("tools:"),yv(" Read, Grep, Glob, Bash")],
    [yk("model:"),yv(" sonnet")],
    [dl("---")],
    [],
    [gln("You are a meticulous code")],
    [gln("reviewer. Flag correctness and")],
    [gln("security first; cite file:line.")],
  ],12.5);
  {const rx=7.65,rw=5.05; let y=1.95;
    const ann=[["Apna fresh context milta hai","Heavy kaam main thread ke bahar hota hai."],["description = trigger","Yahi batata hai main Claude ko — kab delegate karo."],["tools = sandbox","Sirf yahi tools use kar sakta hai — safety."],["Model alag set kar sakte ho","Sahi model, sahi kaam → cost control."]];
    ann.forEach(a=>{card(s,rx,y,rw,0.96,CARD,true);
      s.addText(a[0],{x:rx+0.26,y:y+0.12,w:rw-0.5,h:0.3,fontFace:"Courier New",fontSize:12.5,bold:true,color:CLAYDK,margin:0});
      s.addText(a[1],{x:rx+0.26,y:y+0.44,w:rw-0.5,h:0.45,fontFace:"Arial",fontSize:11,color:SLATE,lineSpacingMultiple:1.08,margin:0});
      y+=1.06;
    });
  }
  s.addText("Is project mein do agents hain: code-reviewer + api-tester — ek-ek .md file.",{x:MX,y:6.0,w:7,h:0.4,fontFace:"Arial",fontSize:11.5,italic:true,color:SLATE,margin:0});
  footer(s,10);

  // =========================================================
  // 11 — 3 SPECIALIST AGENTS
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"robot","Model selection","Sahi kaam ke liye sahi model");
  s.addText("project3_multiagent_code_review — 3 agents, 3 alag models, 3 alag prices",{x:MX,y:1.75,w:12.05,h:0.3,fontFace:"Courier New",fontSize:12,italic:true,color:SLATE,margin:0});
  const agents3=[
    ["security-reviewer","claude-opus-4-8","CRITICAL issue miss karna = disaster. Sabse capable model use karo.",["OWASP Top 10","Hardcoded secrets","SQL injection","Unsafe deserialization"],"~$0.080","B85C3E"],
    ["perf-reviewer","claude-sonnet-4-6","Pattern matching ka kaam hai. Sonnet = quality + cost balance.",["N+1 queries","sync-in-async","Missing DB indexes","Blocking I/O in async"],"~$0.020","185FA5"],
    ["style-reviewer","claude-haiku-4-5","Sabse sasta kaam. Haiku = Opus se 80x sasta.",["PEP 8 violations","Missing type hints","Unclear variable names","Mutable default args"],"~$0.001","3B6D11"],
  ];
  {const cw=3.9,gx=0.28,x0=MX,y=1.98;
    agents3.forEach((a,i)=>{const x=x0+i*(cw+gx);
      card(s,x,y,cw,4.55,CARD,true);
      s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:x+0.25,y:y+0.2,w:cw-0.5,h:0.38,fill:{color:a[5]},rectRadius:0.05});
      s.addText(a[1],{x:x+0.25,y:y+0.2,w:cw-0.5,h:0.38,fontFace:"Courier New",fontSize:11,bold:true,color:WHITE,align:"center",valign:"middle",margin:0});
      s.addText(a[0],{x:x+0.2,y:y+0.72,w:cw-0.4,h:0.35,fontFace:"Courier New",fontSize:12,bold:true,color:INK,margin:0});
      s.addText(a[2],{x:x+0.2,y:y+1.1,w:cw-0.4,h:0.65,fontFace:"Arial",fontSize:11,italic:true,color:SLATE,lineSpacingMultiple:1.12,margin:0});
      let yy=y+1.88; a[3].forEach(t=>{
        s.addImage({data:I.c_arrow,x:x+0.25,y:yy+0.04,w:0.2,h:0.2});
        s.addText(t,{x:x+0.55,y:yy,w:cw-0.75,h:0.38,fontFace:"Arial",fontSize:11,color:INK,valign:"top",margin:0});
        yy+=0.44;
      });
      s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:x+0.5,y:y+3.92,w:cw-1.0,h:0.4,fill:{color:WARM},rectRadius:0.06});
      s.addText("Cost: "+a[4],{x:x+0.5,y:y+3.92,w:cw-1.0,h:0.4,fontFace:"Courier New",fontSize:13,bold:true,color:CLAYDK,align:"center",valign:"middle",margin:0});
    });
  }
  darkBar(s,[{text:"Total per PR review:  ",options:{bold:true,color:WHITE}},{text:"~$0.10  ·  Bina workspace ke: har baar manually type karo.  Workspace ke saath: automatic.",options:{color:ICE}}],6.72,0.58);
  footer(s,11);

  // =========================================================
  // 12 — SKILLS
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"puzzle","Skills","Reusable workflows — ek baar likho, baar baar use karo");
  codeBlock(s,MX,1.85,6.0,3.2,[
    [dl("---"),yc("  skills/add-endpoint/SKILL.md")],
    [yk("name:"),yv(" Add API endpoint")],
    [yk("description:"),yv(" Scaffold a route.")],
    [yv("  Use when adding an endpoint.")],
    [dl("---")],
    [gln("1. Add Pydantic model + route")],
    [gln("2. Wire frontend fetch()")],
    [gln("See reference/conventions.md")],
  ],12);
  s.addText("Skill = folder with SKILL.md + optional scripts/ + reference/.",{x:MX,y:5.12,w:6.0,h:0.4,fontFace:"Arial",fontSize:11.5,italic:true,color:SLATE,margin:0});
  codeBlock(s,MX,5.6,6.0,0.88,[
    [f("skills/"),F("add-endpoint"),f("/  ·  "),f("SKILL.md"),cm("  ·  "),f("reference/conventions.md"),cm("  ·  "),f("scripts/")],
  ],11);
  {const rx=7.2,rw=5.7; let y=1.95;
    const pts=[["Koi install ya restart nahi","Claude folder apne aap detect kar leta hai — drop karo, live ho jaata hai."],["description = trigger","Claude khud decide karta hai kab skill use karni hai."],["Ya /skill-name likhо","Manually bhi run kar sakte ho — /add-endpoint."],["Bundled files saath chalta hai","reference/ + scripts/ progressively load hota hai (agla slide)."]];
    pts.forEach((pt,i)=>{card(s,rx,y,rw,1.06,i%2===0?CARD:WARM,true);
      s.addText(pt[0],{x:rx+0.26,y:y+0.14,w:rw-0.5,h:0.3,fontFace:"Arial",fontSize:13,bold:true,color:CLAYDK,margin:0});
      s.addText(pt[1],{x:rx+0.26,y:y+0.46,w:rw-0.5,h:0.5,fontFace:"Arial",fontSize:11.5,color:SLATE,lineSpacingMultiple:1.08,margin:0});
      y+=1.18;
    });
  }
  footer(s,12);

  // =========================================================
  // 13 — PROGRESSIVE DISCLOSURE
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"eye","Scalability","Progressive disclosure — context bloat kyun nahi hota");
  s.addText([{text:"Context window finite hai.  ",options:{bold:true,color:INK}},{text:"50 skills ka poora text ek saath load karo toh model slow ho jaata hai. Progressive disclosure teen levels mein solve karta hai.",options:{color:SLATE}}],{x:MX,y:1.75,w:12.05,h:0.6,fontFace:"Arial",fontSize:14,lineSpacingMultiple:1.3,margin:0});
  {const lv=[["1","Metadata  —  hamesha context mein","Sirf name + description. Tiny. 200 skills bhi = no bloat.","FBF1EA","B85C3E"],["2","Body  —  trigger hone par load hota hai","Full SKILL.md tab load hota hai jab description match kare. Pehle nahi.","E6F1FB","185FA5"],["3","Bundled files  —  demand pe load","reference/ docs sirf tab load hote hain jab Claude unhe open kare. 500-line spec = 0 tokens until needed.","EAF3DE","3B6D11"]];
    let y=2.52; lv.forEach(l=>{card(s,MX,y,12.05,1.15,l[3]==="FBF1EA"?WARM:l[3]==="E6F1FB"?"E8F2FC":"EAF3DE",true);
      s.addShape(p.shapes.OVAL,{x:MX+0.25,y:y+0.28,w:0.58,h:0.58,fill:{color:l[4]}});
      s.addText(l[0],{x:MX+0.25,y:y+0.28,w:0.58,h:0.58,fontFace:"Arial",fontSize:22,bold:true,color:WHITE,align:"center",valign:"middle",margin:0});
      s.addText(l[1],{x:MX+1.06,y:y+0.12,w:5.5,h:0.35,fontFace:"Arial",fontSize:15,bold:true,color:INK,margin:0});
      s.addText(l[2],{x:MX+1.06,y:y+0.5,w:10.7,h:0.5,fontFace:"Arial",fontSize:12,color:SLATE,lineSpacingMultiple:1.1,margin:0});
      y+=1.28;
    });
  }
  darkBar(s,[{text:"Result:  ",options:{bold:true,color:WHITE}},{text:"Hundreds of skills rakh sakte ho — Claude sirf wahi load karta hai jo actually chahiye. Context lean rehta hai.",options:{color:ICE}}],6.35,0.58);
  footer(s,13);

  // =========================================================
  // 14 — COMMANDS
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"code","Commands","Slash commands — ek shot mein kaam");
  s.addText(".claude/commands/ mein single .md file  ·  /command-name se run karo  ·  Skills se simple (koi folder nahi, koi bundled files nahi)",{x:MX,y:1.75,w:12.05,h:0.35,fontFace:"Arial",fontSize:12.5,italic:true,color:SLATE,margin:0});
  codeBlock(s,MX,2.18,5.9,2.85,[
    [dl("# /check-milestones")],
    [],
    [gln("1. Check which target files exist:")],
    [yv("   state.py → M1  |  graph.py → M2")],
    [yv("   nodes.py → M3-5 | webhook.py → M6")],
    [gln("2. grep for TODO in each file")],
    [gln("3. Output status table:")],
    [yv("   M1 ✅ done  |  M2 ✅  |  M3 ⏳")],
    [gln("4. Suggest next milestone")],
  ],11.5);
  {const rx=7.15,rw=5.6;
    s.addText("Skill vs Command — kab kya use karo",{x:rx,y:2.18,w:rw,h:0.3,fontFace:"Arial",fontSize:13,bold:true,color:CLAYDK,margin:0});
    const comp=[["Skill","Multi-step procedure, bundled files chahiye","add-endpoint · run-app · implement-milestone"],["Command","Quick action, ek hi .md file kaafi","check-milestones · ship-check"]];
    let y=2.56; comp.forEach((c,i)=>{card(s,rx,y,rw,1.55,i===0?CARD:WARM,true);
      s.addText(c[0],{x:rx+0.26,y:y+0.16,w:rw-0.5,h:0.32,fontFace:"Arial",fontSize:15,bold:true,color:CLAYDK,margin:0});
      s.addText(c[1],{x:rx+0.26,y:y+0.52,w:rw-0.5,h:0.32,fontFace:"Arial",fontSize:12,color:SLATE,margin:0});
      s.addText(c[2],{x:rx+0.26,y:y+0.88,w:rw-0.5,h:0.5,fontFace:"Courier New",fontSize:11,color:INK,margin:0});
      y+=1.72;
    });
  }
  darkBar(s,[{text:"Live demo:  ",options:{bold:true,color:WHITE}},{text:"/check-milestones type karo project3 mein → Claude saari 8 files check karta hai, status table banata hai.",options:{color:ICE}}],6.15,0.58);
  footer(s,14);

  // =========================================================
  // 15 — MCP
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"plug","MCP","Claude ko bahar ke tools se connect karo");
  codeBlock(s,MX,1.85,6.3,3.2,[
    [yc("// .mcp.json  (repo root, committed)")],
    [yk("\"mcpServers\""),yv(": {")],
    [yv("  \"filesystem\": {")],
    [yv("    \"command\": "),gln("\"npx\"")],
    [yv("  },")],
    [yv("  \"fetch\": {")],
    [yv("    \"command\": "),gln("\"uvx\""),yv(",")],
    [yv("    \"args\": ["),gln("\"mcp-server-fetch\""),yv("]")],
    [yv("} }")],
  ],12);
  {const rx=7.3,rw=5.4; let y=1.95;
    const steps=[["CLI se add karo","claude mcp add fetch -s project \\\n  -- uvx mcp-server-fetch"],["Ya .mcp.json edit karo","server entry haath se daalo"],["Phir /mcp","status check karo, authenticate karo (OAuth)"]];
    steps.forEach((st,i)=>{card(s,rx,y,rw,1.15,i%2?CARD:WARM,true);
      s.addText(st[0],{x:rx+0.28,y:y+0.14,w:rw-0.5,h:0.3,fontFace:"Arial",fontSize:13,bold:true,color:CLAYDK,margin:0});
      s.addText(st[1],{x:rx+0.28,y:y+0.46,w:rw-0.5,h:0.6,fontFace:"Courier New",fontSize:11,color:INK,lineSpacingMultiple:1.1,valign:"top",margin:0});
      y+=1.27;
    });
  }
  darkBar(s,[{text:"⚠ Tokens kabhi .mcp.json mein mat daalo.  ",options:{bold:true,color:WHITE}},{text:"MCP secrets env vars mein rakho ya personal config mein.",options:{color:ICE}}],5.85,0.58);
  footer(s,15);

  // =========================================================
  // 16 — AGENT vs SKILL vs MCP
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"scale","Decision","Agent vs Skill vs MCP — kab kya use karo");
  const cols=[
    ["robot","Agent","jab isolation chahiye",["Heavy / context-hungry kaam","Constrained role + scoped tools","Alag model ki zaroorat ho"]],
    ["puzzle","Skill","jab procedure chahiye",["Repeatable, step-by-step workflow","Bundled scripts & reference docs","Description se auto-trigger hota hai"]],
    ["plug","MCP","jab bahar jaana ho",["Database, web, GitHub reach karo","Koi bhi tool MCP implement kare",".mcp.json se team share karta hai"]],
  ];
  {const cw=3.85,gx=0.26,x0=MX,y=1.95,ch=4.3;
    cols.forEach((c,i)=>{const x=x0+i*(cw+gx);
      card(s,x,y,cw,ch,CARD,true);
      circle(s,x+cw/2-0.42,y+0.32,0.84,I[c[0]],CLAY);
      s.addText(c[1],{x:x+0.2,y:y+1.28,w:cw-0.4,h:0.4,fontFace:"Arial",fontSize:20,bold:true,color:INK,align:"center",margin:0});
      s.addText(c[2],{x:x+0.2,y:y+1.68,w:cw-0.4,h:0.35,fontFace:"Arial",fontSize:11.5,italic:true,color:CLAYDK,align:"center",margin:0});
      let yy=y+2.2; c[3].forEach(t=>{
        s.addImage({data:I.c_arrow,x:x+0.3,y:yy+0.02,w:0.22,h:0.22});
        s.addText(t,{x:x+0.6,y:yy-0.04,w:cw-0.85,h:0.5,fontFace:"Arial",fontSize:11.5,color:INK,lineSpacingMultiple:1.05,valign:"top",margin:0});
        yy+=0.6;
      });
    });
  }
  s.addText("Yeh compose karte hain: skill agent ke andar chal sakti hai; agent MCP tools use kar sakta hai.",{x:MX,y:6.45,w:12.05,h:0.4,fontFace:"Arial",fontSize:12,italic:true,color:SLATE,align:"center",margin:0});
  footer(s,16);

  // =========================================================
  // 17 — AUTO-FLOW
  // =========================================================
  s=p.addSlide(); s.background={color:DARK};
  s.addImage({data:I.motif,x:9.4,y:1.1,w:4.6,h:4.6,transparency:93});
  circle(s,MX,0.75,0.9,I.bolt,CLAY);
  s.addText("AHA MOMENT",{x:1.75,y:0.78,w:8,h:0.4,fontFace:"Arial",fontSize:14,bold:true,color:CLAY,charSpacing:3,margin:0});
  s.addText("Kuch configure nahi kiya — sab automatic hua",{x:1.72,y:1.12,w:10.5,h:0.65,fontFace:"Arial",fontSize:26,bold:true,color:WHITE,margin:0});
  const flow=[["Session start","CLAUDE.md automatically load → project pata chala","D97757"],["Agent scan","descriptions scan → kab kisko bhejein pata chala","5C6472"],["User bolta hai","message + description match → agent decide hua","5C6472"],["Body load hoti hai","agent ka poora content tab load hota hai, pehle nahi","5C6472"],["Isolation mein run","apne model pe, apne context mein, apne tools se","3F8F5B"]];
  {let y=2.05; flow.forEach((f,i)=>{
    s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:MX,y,w:8.0,h:0.72,fill:{color:"1E1F2E"},rectRadius:0.06});
    s.addShape(p.shapes.OVAL,{x:MX+0.18,y:y+0.18,w:0.36,h:0.36,fill:{color:f[2]}});
    s.addText(String(i+1),{x:MX+0.18,y:y+0.18,w:0.36,h:0.36,fontFace:"Arial",fontSize:13,bold:true,color:WHITE,align:"center",valign:"middle",margin:0});
    s.addText([{text:f[0]+"  —  ",options:{bold:true,color:WHITE}},{text:f[1],options:{color:ICE}}],{x:MX+0.72,y:y+0.06,w:7.0,h:0.58,fontFace:"Arial",fontSize:13,valign:"middle",margin:0});
    if(i<flow.length-1) s.addText("↓",{x:MX+0.36,y:y+0.7,w:0.3,h:0.32,fontFace:"Arial",fontSize:14,color:C_GUIDE,align:"center",margin:0});
    y+=0.9;
  });}
  s.addText("CLAUDE.md = kya hai project  ·  description = kab use karo  ·  body = kaise karo — teen files milke system banati hain.",{x:MX,y:6.72,w:12.0,h:0.5,fontFace:"Arial",fontSize:12,italic:true,color:ICE,lineSpacingMultiple:1.1,margin:0});
  footer(s,17);

  // =========================================================
  // 18 — LIVE DEMO
  // =========================================================
  s=p.addSlide(); s.background={color:DARK};
  s.addImage({data:I.motif,x:9.4,y:1.1,w:4.6,h:4.6,transparency:93});
  circle(s,MX,0.75,0.9,I.play,CLAY);
  s.addText("LIVE DEMO",{x:1.75,y:0.78,w:8,h:0.4,fontFace:"Arial",fontSize:14,bold:true,color:CLAY,charSpacing:3,margin:0});
  s.addText("App chalao",{x:1.72,y:1.12,w:10,h:0.6,fontFace:"Arial",fontSize:30,bold:true,color:WHITE,margin:0});
  codeBlock(s,MX,2.15,7.4,2.2,[
    [({t:"$ ",c:CLAY}),f("pip install -r requirements.txt")],
    [({t:"$ ",c:CLAY}),f("uvicorn backend.main:app --reload")],
    [],
    [gln("→ open http://127.0.0.1:8000")],
  ],13.5);
  {const rx=8.1,rw=4.6; let y=2.2;
    const pts=["UI load hoti hai — \"hello\" type karo, reply aata hai","Status pill dikhata hai demo mode ya live","Koi key nahi chahiye — stage pe safe","Dhyan do: CLAUDE.md + settings.json ne sab karaya, humne nahi"];
    pts.forEach(t=>{s.addShape(p.shapes.OVAL,{x:rx,y:y+0.06,w:0.16,h:0.16,fill:{color:CLAY}});
      s.addText(t,{x:rx+0.34,y:y-0.04,w:rw-0.34,h:0.5,fontFace:"Arial",fontSize:12.5,color:ICE,lineSpacingMultiple:1.05,valign:"top",margin:0});
      y+=0.62;
    });
  }
  s.addText("Optional: Claude se endpoint add karwao → add-endpoint skill use hogi; code-reviewer agent diff pe run karo.",{x:MX,y:5.0,w:12.0,h:0.6,fontFace:"Arial",fontSize:12.5,italic:true,color:ICE,lineSpacingMultiple:1.15,margin:0});
  s.addText("Fail ho jaaye toh: --port 8001, ya curl output dikhao. Live debug max 30 sec — usse zyada nahi.",{x:MX,y:5.75,w:12.0,h:0.5,fontFace:"Arial",fontSize:11,color:"7E8699",margin:0});
  footer(s,18);

  // =========================================================
  // 19 — PRACTICAL: BUGGY CODE DEMO
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"lock","Practical","Agents bugs pakad rahe hain — live dekho");
  s.addText("test_sample_bad_code.py — jaan bujhkar likhe bugs, 3 agents parallel mein review kar rahe hain",{x:MX,y:1.75,w:12.05,h:0.3,fontFace:"Courier New",fontSize:11.5,italic:true,color:SLATE,margin:0});
  {const col1x=MX, col2x=4.58, col3x=8.62, cw=3.62;
    card(s,col1x,2.1,cw,4.4,CARD,true);
    s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:col1x+0.2,y:2.24,w:cw-0.4,h:0.36,fill:{color:"B85C3E"},rectRadius:0.05});
    s.addText("Security  (Opus)",{x:col1x+0.2,y:2.24,w:cw-0.4,h:0.36,fontFace:"Arial",fontSize:12,bold:true,color:WHITE,align:"center",valign:"middle",margin:0});
    const secBugs=[["CRITICAL","Line 9: hardcoded API key","F7768E"],["CRITICAL","Line 14: SQL injection","F7768E"],["HIGH","Line 19: pickle.loads()","F0A860"]];
    let y=2.72; secBugs.forEach(b=>{
      s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:col1x+0.22,y,w:cw-0.44,h:0.9,fill:{color:"FDECEA"},rectRadius:0.05,line:{color:"F7768E",width:0.75}});
      s.addText(b[0],{x:col1x+0.35,y:y+0.08,w:1.2,h:0.25,fontFace:"Arial",fontSize:9.5,bold:true,color:b[2],margin:0});
      s.addText(b[1],{x:col1x+0.35,y:y+0.35,w:cw-0.75,h:0.45,fontFace:"Courier New",fontSize:10,color:INK,lineSpacingMultiple:1.1,margin:0});
      y+=1.04;
    });
    s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:col1x+0.4,y:5.52,w:cw-0.8,h:0.36,fill:{color:WARM},rectRadius:0.05});
    s.addText("→ human_review",{x:col1x+0.4,y:5.52,w:cw-0.8,h:0.36,fontFace:"Arial",fontSize:11,bold:true,color:CLAYDK,align:"center",valign:"middle",margin:0});
    card(s,col2x,2.1,cw,4.4,CARD,true);
    s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:col2x+0.2,y:2.24,w:cw-0.4,h:0.36,fill:{color:"185FA5"},rectRadius:0.05});
    s.addText("Performance  (Sonnet)",{x:col2x+0.2,y:2.24,w:cw-0.4,h:0.36,fontFace:"Arial",fontSize:12,bold:true,color:WHITE,align:"center",valign:"middle",margin:0});
    const perfBugs=[["N+1","Lines 24-27: DB call per item","7AA2F7"],["SYNC_IN_ASYNC","Line 34: requests.get()","7AA2F7"],["INEFFICIENT","Line 41: len() inside loop","7AA2F7"]];
    y=2.72; perfBugs.forEach(b=>{
      s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:col2x+0.22,y,w:cw-0.44,h:0.9,fill:{color:"EBF3FC"},rectRadius:0.05,line:{color:"7AA2F7",width:0.75}});
      s.addText(b[0],{x:col2x+0.35,y:y+0.08,w:1.4,h:0.25,fontFace:"Arial",fontSize:9.5,bold:true,color:b[2],margin:0});
      s.addText(b[1],{x:col2x+0.35,y:y+0.35,w:cw-0.75,h:0.45,fontFace:"Courier New",fontSize:10,color:INK,lineSpacingMultiple:1.1,margin:0});
      y+=1.04;
    });
    s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:col2x+0.4,y:5.52,w:cw-0.8,h:0.36,fill:{color:"E6F1FB"},rectRadius:0.05});
    s.addText("→ request_changes",{x:col2x+0.4,y:5.52,w:cw-0.8,h:0.36,fontFace:"Arial",fontSize:11,bold:true,color:"185FA5",align:"center",valign:"middle",margin:0});
    card(s,col3x,2.1,cw,4.4,CARD,true);
    s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:col3x+0.2,y:2.24,w:cw-0.4,h:0.36,fill:{color:"3B6D11"},rectRadius:0.05});
    s.addText("Style  (Haiku — $0.001)",{x:col3x+0.2,y:2.24,w:cw-0.4,h:0.36,fontFace:"Arial",fontSize:12,bold:true,color:WHITE,align:"center",valign:"middle",margin:0});
    const styleBugs=[["MUTABLE DEF","Line 46: def f(l=[])","9ECE6A"],["UNCLEAR NAME","Line 47: x, s variables","9ECE6A"],["NO TYPE HINTS","All functions missing","9ECE6A"],["PEP8","Line 53: == None","9ECE6A"]];
    y=2.72; styleBugs.forEach(b=>{
      s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:col3x+0.22,y,w:cw-0.44,h:0.62,fill:{color:"EAF3DE"},rectRadius:0.05,line:{color:"9ECE6A",width:0.75}});
      s.addText(b[0],{x:col3x+0.35,y:y+0.04,w:1.6,h:0.22,fontFace:"Arial",fontSize:9.5,bold:true,color:b[2],margin:0});
      s.addText(b[1],{x:col3x+0.35,y:y+0.28,w:cw-0.75,h:0.28,fontFace:"Courier New",fontSize:10,color:INK,margin:0});
      y+=0.76;
    });
    s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:col3x+0.4,y:5.52,w:cw-0.8,h:0.36,fill:{color:"EAF3DE"},rectRadius:0.05});
    s.addText("→ request_changes",{x:col3x+0.4,y:5.52,w:cw-0.8,h:0.36,fontFace:"Arial",fontSize:11,bold:true,color:"3B6D11",align:"center",valign:"middle",margin:0});
  }
  darkBar(s,[{text:"Total cost: $0.10  ·  ",options:{bold:true,color:WHITE}},{text:"3 agents PARALLEL chale  ·  Security ne CRITICAL pakda → merge block  ·  Sab workspace config se automatic.",options:{color:ICE}}],6.72,0.58);
  footer(s,19);

  // =========================================================
  // 20 — HANDS-ON LAB
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  circle(s,MX,0.5,0.78,I.hand,CLAY);
  s.addText("TUMHARI BAARI  ·  ~5 MIN",{x:1.62,y:0.5,w:10,h:0.3,fontFace:"Arial",fontSize:12.5,bold:true,color:CLAY,charSpacing:2,valign:"middle",margin:0});
  s.addText("Haath se karo: apni pehli Skill banao",{x:1.6,y:0.8,w:11.2,h:0.55,fontFace:"Arial",fontSize:27,bold:true,color:INK,valign:"middle",margin:0});
  {const steps=[["1","Folder banao","mkdir -p .claude/skills/greet"],["2","SKILL.md daalo","name + ek line description (yahi trigger hai)"],["3","Use karo","type /greet — ya likho \"welcome teammate Sara\""]];
    let y=1.9; steps.forEach(st=>{card(s,MX,y,6.1,1.15,CARD,true);
      s.addShape(p.shapes.OVAL,{x:MX+0.25,y:y+0.3,w:0.55,h:0.55,fill:{color:CLAY}});
      s.addText(st[0],{x:MX+0.25,y:y+0.3,w:0.55,h:0.55,fontFace:"Arial",fontSize:22,bold:true,color:WHITE,align:"center",valign:"middle",margin:0});
      s.addText(st[1],{x:MX+1.0,y:y+0.2,w:4.9,h:0.35,fontFace:"Arial",fontSize:15,bold:true,color:INK,margin:0});
      s.addText(st[2],{x:MX+1.0,y:y+0.56,w:4.95,h:0.45,fontFace:"Courier New",fontSize:11,color:SLATE,lineSpacingMultiple:1.05,valign:"top",margin:0});
      y+=1.3;
    });
  }
  codeBlock(s,7.05,1.9,5.65,3.75,[
    [dl("---"),yc("  .claude/skills/greet/SKILL.md")],
    [yk("name:"),yv(" Greet the user")],
    [yk("description:"),yv(" Write a short,")],
    [yv("  friendly welcome for a new")],
    [yv("  teammate. Use to greet or")],
    [yv("  onboard someone.")],
    [dl("---")],
    [],
    [gln("# Greet a new teammate")],
    [gln("1. Welcome them by name.")],
    [gln("2. Point to README + the guide.")],
    [gln("3. Keep it 3-4 sentences.")],
  ],12);
  s.addText("Koi install nahi, koi restart nahi — Claude folder apne aap detect kar leta hai.   Full steps: bootcamp/LAB.md",{x:MX,y:6.45,w:12,h:0.4,fontFace:"Arial",fontSize:12,italic:true,color:SLATE,align:"center",margin:0});
  footer(s,20);

  // =========================================================
  // 21 — ZERO TO GITHUB
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"term","Setup flow","Zero se GitHub tak — 10 steps");
  s.addText("Yeh wahi steps hain jo tumne aaj khud kiye — pehle workspace, phir git, phir GitHub.",{x:MX,y:1.75,w:12.05,h:0.3,fontFace:"Arial",fontSize:12.5,italic:true,color:SLATE,margin:0});
  {
    const col1=[
      ["1","app.py","tumhara code — kuch nahi badla","3F8F5B"],
      ["2","CLAUDE.md","project memory banao","D97757"],
      ["3",".gitignore","secrets ko bahar rakho","D97757"],
      ["4",".claude/settings.json","allow / deny rules","D97757"],
      ["5",".claude/agents/*.md","specialist agents add karo","D97757"],
      ["6",".claude/skills/*/","reusable workflows","D97757"],
      ["7",".claude/commands/*.md","slash commands","D97757"],
      ["8",".mcp.json","bahar ke tools connect karo","D97757"],
    ];
    const col2=[
      ["9","git init + add + commit","workspace ko version control mein daalo","185FA5"],
      ["10","git push origin main","GitHub pe — team share ke liye ready","185FA5"],
    ];
    let y=2.12;
    col1.forEach((r,i)=>{
      const bg=i===0?"EAF3DE":i%2===0?CARD:WARM;
      s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:MX,y,w:7.9,h:0.58,fill:{color:bg},rectRadius:0.06});
      s.addShape(p.shapes.OVAL,{x:MX+0.14,y:y+0.12,w:0.34,h:0.34,fill:{color:r[3]}});
      s.addText(r[0],{x:MX+0.14,y:y+0.12,w:0.34,h:0.34,fontFace:"Arial",fontSize:12,bold:true,color:WHITE,align:"center",valign:"middle",margin:0});
      s.addText(r[1]+"  ",{x:MX+0.62,y:y+0.06,w:2.2,h:0.46,fontFace:"Courier New",fontSize:11.5,bold:true,color:r[3]==="3F8F5B"?GREENBADGE:CLAYDK,valign:"middle",margin:0});
      s.addText(r[2],{x:MX+2.86,y:y+0.06,w:4.8,h:0.46,fontFace:"Arial",fontSize:11,color:SLATE,valign:"middle",margin:0});
      y+=0.64;
    });
    s.addShape(p.shapes.LINE,{x:MX,y:y+0.05,w:7.9,h:0,line:{color:BORDER,width:1}});
    y+=0.22;
    col2.forEach(r=>{
      s.addShape(p.shapes.ROUNDED_RECTANGLE,{x:MX,y,w:7.9,h:0.58,fill:{color:"E8F2FC"},rectRadius:0.06,line:{color:"7AA2F7",width:0.8}});
      s.addShape(p.shapes.OVAL,{x:MX+0.14,y:y+0.12,w:0.34,h:0.34,fill:{color:r[3]}});
      s.addText(r[0],{x:MX+0.14,y:y+0.12,w:0.34,h:0.34,fontFace:"Arial",fontSize:12,bold:true,color:WHITE,align:"center",valign:"middle",margin:0});
      s.addText(r[1]+"  ",{x:MX+0.62,y:y+0.06,w:2.9,h:0.46,fontFace:"Courier New",fontSize:11.5,bold:true,color:"185FA5",valign:"middle",margin:0});
      s.addText(r[2],{x:MX+3.56,y:y+0.06,w:4.1,h:0.46,fontFace:"Arial",fontSize:11,color:SLATE,valign:"middle",margin:0});
      y+=0.64;
    });
    card(s,9.0,2.12,3.7,4.35,CODEBG,true);
    s.addText("Git commands",{x:9.15,y:2.28,w:3.4,h:0.3,fontFace:"Arial",fontSize:12,bold:true,color:CLAY,margin:0});
    const cmds=[
      ["git init","naya repo banao"],
      ["git add .claude/","workspace stage karo"],
      ["git add CLAUDE.md","memory stage karo"],
      ["git add .mcp.json","mcp config"],
      ["git add app.py","code"],
      ["# .env gitignored hai","safe!"],
      ["git commit -m","\"add workspace\""],
      ["gh repo create","GitHub pe banao"],
      ["git push -u","origin main"],
    ];
    let cy=2.7; cmds.forEach(c=>{
      s.addText(c[0],{x:9.18,y:cy,w:2.1,h:0.28,fontFace:"Courier New",fontSize:10.5,color:c[0].startsWith("#")?"6B7494":C_GREEN,bold:!c[0].startsWith("#"),margin:0});
      s.addText(c[1],{x:11.3,y:cy,w:1.3,h:0.28,fontFace:"Arial",fontSize:10,color:ICE,margin:0});
      cy+=0.36;
    });
  }
  darkBar(s,[{text:"Clone karo — instantly productive:  ",options:{bold:true,color:WHITE}},{text:"git clone → Claude Code kholo → CLAUDE.md load → workspace ready. Zero setup.",options:{color:ICE}}],6.72,0.58);
  footer(s,21);

  // =========================================================
  // 22 — RECAP
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"check","Yaad rakho","5 cheezein jo leke jaani hain");
  const tk=[
    ["Workspace = code + committed .claude/ layer","Tumhara code untouched; .claude/ layer Claude ko project sikhati hai."],
    ["CLAUDE.md = memory — hamesha load, lean rakho","200 lines se chhota. Commands + conventions + capabilities."],
    ["Agents isolate · Skills package · MCP connect","Kaam ke hisaab se choose karo; yeh compose bhi karte hain."],
    ["Progressive disclosure se scale hota hai","Metadata hamesha · body trigger pe · reference files demand pe."],
    ["Commit karo .claude/ — .env & *.local bahar rakho","Setup share karo; secrets kabhi share mat karo."],
  ];
  {let y=1.95; tk.forEach((t,i)=>{
    s.addShape(p.shapes.OVAL,{x:MX,y,w:0.5,h:0.5,fill:{color:CLAY}});
    s.addText(String(i+1),{x:MX,y,w:0.5,h:0.5,fontFace:"Arial",fontSize:16,bold:true,color:WHITE,align:"center",valign:"middle",margin:0});
    s.addText(t[0],{x:MX+0.75,y:y-0.04,w:11.5,h:0.35,fontFace:"Arial",fontSize:15.5,bold:true,color:INK,margin:0});
    s.addText(t[1],{x:MX+0.75,y:y+0.32,w:11.5,h:0.35,fontFace:"Arial",fontSize:11.5,color:SLATE,margin:0});
    y+=0.92;
  });}
  footer(s,22);

  // =========================================================
  // 23 — PROJECT3 REAL-WORLD
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"robot","Real-world","Multi-Agent Code Review — production mein workspace");
  codeBlock(s,MX,1.85,6.2,3.5,[
    [yc("# GitHub PR khula → LangGraph Supervisor")],
    [],
    [({t:"  ┌─ ",c:C_GUIDE}),({t:"Security Agent",c:C_PURP,b:true}),({t:"  (Opus)",c:C_COMMENT})],
    [({t:"PR─┤─ ",c:C_GUIDE}),({t:"Perf Agent    ",c:C_KEY,b:true}),({t:"  (Sonnet)",c:C_COMMENT})],
    [({t:"  └─ ",c:C_GUIDE}),({t:"Style Agent   ",c:C_GREEN,b:true}),({t:"  (Haiku)",c:C_COMMENT})],
    [],
    [({t:"       ↓ parallel  →  Synthesizer",c:C_GUIDE})],
    [({t:"       CRITICAL? → ",c:C_GUIDE}),({t:"human_review",c:"F7768E",b:true})],
    [({t:"       else      → ",c:C_GUIDE}),({t:"post_github",c:C_GREEN,b:true})],
  ],12);
  {const rx=7.2,rw=5.5; let y=1.95;
    const items=[["agents/security-reviewer.md","Opus — OWASP Top 10, HMAC, secrets"],["agents/perf-reviewer.md","Sonnet — N+1, sync_in_async"],["agents/style-reviewer.md","Haiku — PEP8, type hints"],["agents/graph-debugger.md","LangGraph routing debug karta hai"],["skills/implement-milestone/","Step-by-step milestone guide"],["skills/run-app/","Install + server launch karo"]];
    items.forEach((it,i)=>{card(s,rx,y,rw,0.62,i<4?CARD:WARM,false);
      s.addText(it[0],{x:rx+0.25,y:y+0.08,w:rw-0.5,h:0.26,fontFace:"Courier New",fontSize:10.5,bold:true,color:CLAYDK,margin:0});
      s.addText(it[1],{x:rx+0.25,y:y+0.34,w:rw-0.5,h:0.22,fontFace:"Arial",fontSize:10,color:SLATE,margin:0});
      y+=0.70;
    });
  }
  darkBar(s,[{text:"PR review cost:  ",options:{bold:true,color:WHITE}},{text:"Security ~$0.08 (Opus)  ·  Perf ~$0.02 (Sonnet)  ·  Style ~$0.001 (Haiku)  ·  Total ~$0.10",options:{color:ICE}}],6.2,0.55);
  footer(s,23);

  // =========================================================
  // 24 — GSD CONNECTION
  // =========================================================
  s=p.addSlide(); s.background={color:LIGHT};
  header(s,"brain","Badi picture","GSD System = Workspace, alag naam");
  s.addText([{text:"\"Get Shit Done\" (GSD) system  ",options:{bold:true,color:INK}},{text:"3 disciplines define karta hai AI-assisted dev ke liye. Claude Code workspace teeno automatically implement karta hai.",options:{color:SLATE}}],{x:MX,y:1.75,w:12.05,h:0.7,fontFace:"Arial",fontSize:14.5,lineSpacingMultiple:1.3,valign:"top",margin:0});
  const gsd=[["Meta-Prompting","AI ko sirf WHAT nahi, HOW sochna bhi batao","CLAUDE.md + agent frontmatter\n→ role, reasoning, constraints"],["Context Engineering","Project knowledge persist aur structure karo","CLAUDE.md har session load;\nSkills sirf relevant hone pe"],["Spec-Driven Dev","Pehle spec likho, phir execute karo","SKILL.md pehle define hota hai;\nClaude us spec se execute karta hai"]];
  {const cw=3.85,gx=0.26,x0=MX,y=2.65,ch=3.2;
    gsd.forEach((g,i)=>{const x=x0+i*(cw+gx);
      card(s,x,y,cw,ch,i===0?WARM:CARD,true);
      s.addShape(p.shapes.OVAL,{x:x+cw/2-0.35,y:y+0.22,w:0.7,h:0.7,fill:{color:CLAY}});
      s.addText(String(i+1),{x:x+cw/2-0.35,y:y+0.22,w:0.7,h:0.7,fontFace:"Arial",fontSize:24,bold:true,color:WHITE,align:"center",valign:"middle",margin:0});
      s.addText(g[0],{x:x+0.2,y:y+1.08,w:cw-0.4,h:0.4,fontFace:"Arial",fontSize:15,bold:true,color:INK,align:"center",margin:0});
      s.addText(g[1],{x:x+0.2,y:y+1.5,w:cw-0.4,h:0.5,fontFace:"Arial",fontSize:11,italic:true,color:SLATE,align:"center",lineSpacingMultiple:1.1,margin:0});
      s.addShape(p.shapes.LINE,{x:x+0.6,y:y+2.08,w:cw-1.2,h:0,line:{color:BORDER,width:1}});
      s.addText("→ "+g[2],{x:x+0.2,y:y+2.18,w:cw-0.4,h:0.85,fontFace:"Courier New",fontSize:10.5,color:CLAYDK,lineSpacingMultiple:1.2,valign:"top",margin:0});
    });
  }
  darkBar(s,[{text:"Result:  ",options:{bold:true,color:WHITE}},{text:"Setup time 10-15 min → 60 sec se kum  ·  Rework 30-50% → 10-15%  ·  3 mahine mein 30-60% speed up",options:{color:ICE}}],6.05,0.58);
  footer(s,24);

  // =========================================================
  // 25 — Q&A / CLOSE
  // =========================================================
  s=p.addSlide(); s.background={color:DARK};
  s.addImage({data:I.motif,x:9.3,y:1.2,w:4.7,h:4.7,transparency:92});
  s.addText("SHUKRIYA",{x:MX,y:1.7,w:10,h:0.4,fontFace:"Arial",fontSize:14,bold:true,color:CLAY,charSpacing:3,margin:0});
  s.addText("Koi sawaal?",{x:MX-0.02,y:2.1,w:11,h:0.9,fontFace:"Arial",fontSize:46,bold:true,color:WHITE,margin:0});
  s.addText("Sab kuch repo mein hai — jao aur banao:",{x:MX,y:3.25,w:11,h:0.4,fontFace:"Arial",fontSize:15,color:ICE,margin:0});
  {const res=[["README.md","jaldi shuru karo"],["WORKSPACE_GUIDE.md","poora walkthrough"],["bootcamp/LAB.md","haath se karne ke steps"],["bootcamp/CHEATSHEET.md","ek page reference"]];
    let y=3.95; res.forEach(r=>{s.addShape(p.shapes.OVAL,{x:MX,y:y+0.05,w:0.16,h:0.16,fill:{color:CLAY}});
      s.addText([{text:r[0]+"   ",options:{bold:true,color:WHITE,fontFace:"Courier New",fontSize:13}},{text:"— "+r[1],options:{color:ICE}}],{x:MX+0.34,y:y-0.05,w:9,h:0.4,fontFace:"Arial",fontSize:13.5,valign:"middle",margin:0});
      y+=0.55;
    });
  }
  s.addShape(p.shapes.LINE,{x:MX,y:6.45,w:2.0,h:0,line:{color:CLAY,width:2}});
  s.addText("Friday Bootcamp  ·  Claude Code Workspace",{x:MX,y:6.6,w:10,h:0.4,fontFace:"Arial",fontSize:12,color:ICE,margin:0});
  s.addNotes(NOTES[25]);

  await p.writeFile({fileName:"/Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Projects/workspace_demo/bootcamp/Workspace_Bootcamp.pptx"});
  console.log("DECK WRITTEN — 25 slides (Hinglish)");
})().catch(e=>{console.error(e);process.exit(1);});
