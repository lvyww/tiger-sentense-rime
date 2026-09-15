-- Run this *same* probe in separate Lua processes for old and new sources.
-- Stable behavior-only serialization deliberately ignores cache/layout fields.
local source, data, mode, random_cases = arg[1], arg[2], arg[3], tonumber(arg[4]) or 20
package.path=source.."/lua/?.lua;"..package.path
rime_api={get_user_data_dir=function()return data end}
os.time=function()return 1800000000 end
local sentence=require("tiger_sentence")
if arg[5] and sentence.set_memory_profile then assert(sentence.set_memory_profile(arg[5])) end
local trim_every=tonumber(arg[6]) or 0
if arg[7]=="legacy-ranking" and sentence.set_decoder_parameters_for_test then
    sentence.set_decoder_parameters_for_test({canonical_code_reward=0,
        lexical_prior_weight=0,canonical_isolation_factor=1,
        canonical_isolation_min_code_length=2})
end
sentence.ensure_lexicon(nil);sentence.set_model_enabled(mode~="none")
local model=sentence.model_status()
assert(mode=="none" or (model.loaded and model.format=="TCSKNM02"),"required paged model was not loaded")
local function canonical(value)
    local kind=type(value)
    if kind=="nil" then return "nil" end
    if kind=="boolean" then return tostring(value) end
    if kind=="number" then assert(value==value and math.abs(value)<math.huge,"nonfinite snapshot value");return string.format("%a",value==0 and 0 or value) end
    if kind=="string" then return string.format("%q",value):gsub("\n","\\n") end
    assert(kind=="table","unsupported snapshot value")
    local keys={};for k in pairs(value)do keys[#keys+1]=k end
    table.sort(keys,function(a,b)if type(a)==type(b)then return a<b end;return type(a)<type(b)end)
    local parts={}
    for _,k in ipairs(keys)do parts[#parts+1]="["..canonical(k).."]="..canonical(value[k]) end
    return "{"..table.concat(parts,",").."}"
end
local path_nodes, path_ids, path_seen
local function path(item)
    if not item then return 0 end
    if path_seen[item] then return path_seen[item] end
    local parent=path(item.previous)
    local value={raw=item.raw_length,text_length=item.text_length,text=item.text,
        prev2=item.prev2,prev1=item.prev1,score=item.score,mass=item.mass_score or item.score,
        learning=item.learning_score or 0,potential=item.learning_potential or 0,
        rank=item.max_rank or 1,edges=item.edge_count or 0,supplement=item.supplement_score or 0,parent=parent}
    local key=canonical(value)
    local id=path_ids[key]
    if not id then id=#path_nodes+1;path_ids[key]=id;path_nodes[id]=value end
    path_seen[item]=id
    return id
end

local function candidates(items,display)
    local values={}
    for i,item in ipairs(items or {})do
        values[i]={text=item.text,score=item.score,confidence=item.confidence_score or item.score,
            learning=item.learning_score or 0,supplement=item.supplement_score or 0,
            rank=item.max_rank or 1,edges=item.edge_count or 0,path=path(item.path),
            segmented=display and item.segmented or nil}
    end
    return values
end
local count,cpu=0,0
local function capture(label,raw,evidence,required,lock)
    if trim_every > 0 and count % trim_every == 0 and sentence.trim_memory then sentence.trim_memory() end
    local started=os.clock()
    local result=sentence.decode(raw,evidence,required or "",lock)
    cpu=cpu+(os.clock()-started)
    local e=result.early_commit_evidence or {}
    local prefixes={}
    for i,p in ipairs(e.prefixes or {})do
        prefixes[i]={text=p.text,raw=p.raw_length,share=p.share,boundary_share=p.boundary_share,closed=p.boundary_closed}
    end
    path_nodes,path_ids,path_seen={},{},{}
    local menu=candidates(result,true)
    local pool=candidates(result._confidence_candidates,false)
    local snapshot={label=label,raw=raw,menu=menu,pool=pool,paths=path_nodes,
        learning=result.learning_affected or false,truncated=result._completed_truncated or false,
        evidence={prefixes=prefixes,proposal=e.proposal or "",share=e.proposal_share or 0,raw_lengths=e.raw_lengths or {},
            truncated=e.confidence_truncated or false,neutral_tail=e.neutral_incomplete_tail or false,
            merged_tail=e.merged_incomplete_tail or false,neutral_low=e.neutral_low_confidence or false}}
    io.write(canonical(snapshot),"\n");count=count+1
    return result
end
local samples={"ot","ueot","tucbot","ueot12","jqtusotuqiueottu","awmenamcunta",
    "jeumbauefaalhngyoehiyfbmvmxfzbflrl","nnczggqrrjrrltwwbwkedmkswgjgiuapnphbszbp"}
local seed=20260914
for i=1,random_cases do
    local chars={}
    for j=1,40 do seed=seed*48271%2147483647;chars[j]=string.char(97+seed%26) end
    samples[#samples+1]=table.concat(chars)
end
local learning=sentence.learning
local events={}
for _,event in ipairs({{"tu","我",""},{"ueot","的是",""},{"tucbot","我不是",""},
    {"rlrl","了了","前"},{"rlrl","了了","后"}})do
    events[#events+1]={code=event[1],text=event[2],context=event[3],mode="snapshot",time=os.time()}
end
for i=1,300 do
    events[#events+1]={code="ueot"..string.format("%04d",i),text="的是甲",context="",mode="snapshot",time=os.time()}
end
for _,learned in ipairs({false,true})do
    for _,duplicate in ipairs({false,true})do
        sentence.set_allow_duplicate_single({get_option=function()return duplicate end})
        sentence.set_learning_for_test(learned and learning.runtime_index(events,os.time()) or nil,learned and "snapshot" or "")
        local group=tostring(learned).."/"..tostring(duplicate)
        for case,raw in ipairs(samples)do
            local label=group.."/"..case
            sentence.reset_decode_cache()
            for n=1,#raw do
                local prefix=raw:sub(1,n)
                capture(label.."/menu",prefix,false)
                capture(label.."/evidence",prefix,true)
            end
            for n=#raw-1,0,-1 do capture(label.."/delete",raw:sub(1,n),true) end
            capture(label.."/paste",raw,true)
            capture(label.."/middle-edit",raw:sub(1,3).."a"..raw:sub(5),true)
            if #raw>5 then
                local n=math.max(2,math.floor(#raw/2))
                local prefix=raw:sub(1,n)
                local result=capture(label.."/lock-base",prefix,false)
                local selected=result[math.min(2,#result)]
                if selected and selected.path then
                    local boundaries,node={},selected.path
                    while node and (node.raw_length or 0)>0 do
                        table.insert(boundaries,1,node.raw_length..","..node.text_length..";")
                        node=node.previous
                    end
                    local lock={raw=prefix,text=selected.text,boundaries=table.concat(boundaries)}
                    for finish=n,#raw do capture(label.."/locked",raw:sub(1,finish),true,selected.text,lock) end
                    for finish=#raw-1,n,-1 do capture(label.."/locked-delete",raw:sub(1,finish),true,selected.text,lock) end
                    sentence.reset_decode_cache()
                end
            end
        end
    end
end
io.stderr:write(string.format('{"snapshots":%d,"decode_cpu_ms":%.3f,"model":"%s","model_bytes":%d}\n',
    count,cpu*1000,model.loaded and model.format or "none",model.bytes or 0))
