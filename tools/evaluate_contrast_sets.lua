-- Evaluate the sentence decoder on Markdown contrast lists.
--
-- Usage:
--   lua tools/evaluate_contrast_sets.lua REPO_ROOT FILE... [--limit N]
--
-- Each input file is expected to contain bullets in the form:
--   - target text ▸ reported output
--
-- The tool reconstructs TigerSentence's normal per-character input stream
-- from tiger_sentence.codes.txt, decodes it in one pass, and reports Top-K
-- coverage.  It intentionally measures final decoding, not Rime's key-event
-- early-commit protocol; a reported-output mismatch is called out separately.

local repo = arg[1] or "."
local files = {}
local limit = math.huge
local dump_path = nil
local parameters = {}
local selected_case = nil
local index = 2
while index <= #arg do
    if arg[index] == "--limit" then
        limit = tonumber(arg[index + 1]) or limit
        index = index + 2
    elseif arg[index] == "--dump-candidates" then
        dump_path = arg[index + 1]
        index = index + 2
    elseif arg[index] == "--set" then
        local name, value = (arg[index + 1] or ""):match("^([%w_]+)=([%+%-%.%deE]+)$")
        if not name or not tonumber(value) then
            io.stderr:write("--set expects NAME=NUMBER\n")
            os.exit(2)
        end
        parameters[name] = tonumber(value)
        index = index + 2
    elseif arg[index] == "--case" then
        selected_case = tonumber(arg[index + 1])
        if not selected_case or selected_case < 1 then
            io.stderr:write("--case expects a positive list index\n")
            os.exit(2)
        end
        index = index + 2
    else
        files[#files + 1] = arg[index]
        index = index + 1
    end
end
if #files == 0 then
    io.stderr:write("at least one contrast Markdown file is required\n")
    os.exit(2)
end

package.path = repo .. "/lua/?.lua;" .. package.path
rime_api = {
    get_user_data_dir = function() return repo end
}

local function utf_chars(text)
    local result = {}
    for _, codepoint in utf8.codes(text) do
        result[#result + 1] = utf8.char(codepoint)
    end
    return result
end

local function read_lines(path)
    local handle, err = io.open(path, "rb")
    if not handle then error(err) end
    local content = handle:read("*a") or ""
    handle:close()
    content = content:gsub("^\239\187\191", ""):gsub("\r\n", "\n"):gsub("\r", "\n")
    local lines = {}
    for line in (content .. "\n"):gmatch("(.-)\n") do
        lines[#lines + 1] = line
    end
    return lines
end

local function build_encoder(path)
    local exact = {}
    local character_codes = {}
    for _, line in ipairs(read_lines(path)) do
        if line ~= "" and line:sub(1, 1) ~= "#" then
            local text, code = line:match("^(%S+)%s+(%S+)")
            if text and code and code:match("^[a-z]+$") then
                local bucket = exact[code]
                if not bucket then bucket = {}; exact[code] = bucket end
                bucket[#bucket + 1] = text
                if utf8.len(text) == 1 then
                    local codes = character_codes[text]
                    if not codes then codes = {}; character_codes[text] = codes end
                    codes[#codes + 1] = code
                end
            end
        end
    end

    local encoder = {}
    for character, codes in pairs(character_codes) do
        local best_first, best_any
        for _, code in ipairs(codes) do
            if #code >= 2 then
                if not best_any or #code < #best_any then best_any = code end
                if exact[code][1] == character and
                    (not best_first or #code < #best_first) then
                    best_first = code
                end
            end
        end
        encoder[character] = best_first or best_any
    end
    return encoder
end

local function load_cases(paths)
    local cases = {}
    for _, path in ipairs(paths) do
        local domain = "unknown"
        local case_index = 0
        for _, line in ipairs(read_lines(path)) do
            local heading = line:match("^##%s+(.+)%(") or
                line:match("^##%s+(.+)（")
            if heading then domain = heading end
            local target, reported = line:match("^%-%s+(.+)%s+▸%s+(.+)%s*$")
            if target and reported then
                case_index = case_index + 1
                if not selected_case or selected_case == case_index then
                    cases[#cases + 1] = {
                        source = path,
                        source_index = case_index,
                        domain = domain,
                        target = target:gsub("%s+$", ""),
                        reported = reported:gsub("%s+$", "")
                    }
                    if #cases >= limit then return cases end
                end
            end
        end
    end
    return cases
end

local function encode(text, encoder)
    local chunks = {}
    for _, character in ipairs(utf_chars(text)) do
        local code = encoder[character]
        if not code then return nil, character end
        chunks[#chunks + 1] = code
    end
    return table.concat(chunks)
end

local function path_edges(raw, path)
    local reversed = {}
    while path and (path.raw_length or 0) > 0 do
        local start = path.previous and (path.previous.raw_length or 0) or 0
        reversed[#reversed + 1] = raw:sub(start + 1, path.raw_length) .. "=" ..
            table.concat(path.edge_chars or {})
        path = path.previous
    end
    local result = {}
    for i = #reversed, 1, -1 do result[#result + 1] = reversed[i] end
    return table.concat(result, "|")
end

local sentence = require("tiger_sentence")
sentence.ensure_lexicon(nil)
sentence.set_decoder_parameters_for_test(parameters)
local status = sentence.model_status()
if not status.loaded then
    io.stderr:write("production model is required: " .. tostring(status.error) .. "\n")
    os.exit(2)
end

local encoder = build_encoder(repo .. "/tiger_sentence.codes.txt")
local cases = load_cases(files)
local totals = {
    cases = #cases,
    encodable = 0,
    top1 = 0,
    top5 = 0,
    top20 = 0,
    reported_match = 0,
    target_missing = 0,
    total_ms = 0
}
local domains = {}
local misses = {}
local dump = nil
if dump_path then
    dump = assert(io.open(dump_path, "wb"))
    dump:write("case\tdomain\ttarget\treported\traw\trank\ttext\tscore\tconfidence\tsupplement\tcode\tlexical\tlearning\tisolation\tedges\tmax_rank\tsegmented\tpath_edges\n")
end

for case_index, item in ipairs(cases) do
    local raw, missing = encode(item.target, encoder)
    if not raw then
        item.error = "no code for " .. missing
    else
        totals.encodable = totals.encodable + 1
        sentence.reset_decode_cache()
        local started = os.clock()
        local results = sentence.decode_full(raw, false, "")
        totals.total_ms = totals.total_ms + (os.clock() - started) * 1000
        local target_rank
        for rank = 1, #results do
            if results[rank].text == item.target then
                target_rank = rank
                break
            end
        end
        item.raw = raw
        item.actual = results[1] and results[1].text or ""
        item.target_rank = target_rank
        if dump then
            for rank = 1, #results do
                local candidate = results[rank]
                dump:write(table.concat({
                    tostring(case_index), item.domain, item.target, item.reported,
                    raw, tostring(rank), candidate.text,
                    string.format("%.17g", candidate.score or 0),
                    string.format("%.17g", candidate.confidence_score or candidate.score or 0),
                    string.format("%.17g", candidate.supplement_score or 0),
                    string.format("%.17g", candidate.code_score or 0),
                    string.format("%.17g", candidate.lexical_score or 0),
                    string.format("%.17g", candidate.learning_score or 0),
                    string.format("%.17g", sentence.path_isolation_penalty(candidate.path)),
                    tostring(candidate.edge_count or 0),
                    tostring(candidate.max_rank or 1),
                    candidate.segmented or "",
                    path_edges(raw, candidate.path)
                }, "\t"), "\n")
            end
        end
        if target_rank == 1 then totals.top1 = totals.top1 + 1 end
        if target_rank and target_rank <= 5 then totals.top5 = totals.top5 + 1 end
        if target_rank and target_rank <= 20 then totals.top20 = totals.top20 + 1 end
        if not target_rank then totals.target_missing = totals.target_missing + 1 end
        if item.actual == item.reported then totals.reported_match = totals.reported_match + 1 end
        if target_rank ~= 1 then misses[#misses + 1] = item end

        local domain = domains[item.domain]
        if not domain then
            domain = {cases=0, top1=0, top5=0, top20=0}
            domains[item.domain] = domain
        end
        domain.cases = domain.cases + 1
        if target_rank == 1 then domain.top1 = domain.top1 + 1 end
        if target_rank and target_rank <= 5 then domain.top5 = domain.top5 + 1 end
        if target_rank and target_rank <= 20 then domain.top20 = domain.top20 + 1 end
    end
    if case_index % 50 == 0 then
        io.stderr:write(string.format("\rdecoded %d/%d", case_index, #cases))
        io.stderr:flush()
    end
end
if #cases >= 50 then io.stderr:write("\n") end
if dump then dump:close() end

local function percent(value, denominator)
    if denominator == 0 then return 0 end
    return 100 * value / denominator
end

print(string.format(
    "cases=%d encodable=%d top1=%d (%.2f%%) top5=%d (%.2f%%) top20=%d (%.2f%%) missing=%d reported_match=%d mean_ms=%.3f",
    totals.cases, totals.encodable,
    totals.top1, percent(totals.top1, totals.encodable),
    totals.top5, percent(totals.top5, totals.encodable),
    totals.top20, percent(totals.top20, totals.encodable),
    totals.target_missing, totals.reported_match,
    totals.encodable > 0 and totals.total_ms / totals.encodable or 0))
local active = sentence.decoder_parameters()
print(string.format(
    "parameters beam=%d long_beam=%d char_reward=%.4g rank_penalty=%.4g canonical_reward=%.4g lexical_weight=%.4g isolation_threshold=%d isolation_lambda=%.4g canonical_isolation_factor=%.4g canonical_isolation_min_code_length=%d",
    active.beam_width, active.long_input_beam_width,
    active.emitted_character_reward, active.rank_penalty,
    active.canonical_code_reward, active.lexical_prior_weight, active.isolation_threshold,
    active.isolation_lambda, active.canonical_isolation_factor,
    active.canonical_isolation_min_code_length))

local domain_names = {}
for name in pairs(domains) do domain_names[#domain_names + 1] = name end
table.sort(domain_names)
for _, name in ipairs(domain_names) do
    local value = domains[name]
    print(string.format("domain=%s cases=%d top1=%.2f%% top5=%.2f%% top20=%.2f%%",
        name, value.cases,
        percent(value.top1, value.cases),
        percent(value.top5, value.cases),
        percent(value.top20, value.cases)))
end

for i = 1, math.min(30, #misses) do
    local item = misses[i]
    print(string.format("MISS\t%s\t%s\t%s\t%s\t%s",
        item.domain, item.target, item.actual or "", item.target_rank or "-", item.raw or item.error))
end
