-- Guard the scheme's intentional multi-character shorthand edges while
-- evaluating shape-code priors.
--
-- Usage:
--   lua tools/evaluate_phrase_edges.lua REPO_ROOT [CANONICAL_WEIGHT]

local repo = arg[1] or "."
local weight = tonumber(arg[2]) or 0
package.path = repo .. "/lua/?.lua;" .. package.path
rime_api = { get_user_data_dir = function() return repo end }

local sentence = require("tiger_sentence")
sentence.ensure_lexicon(nil)
if not sentence.model_status().loaded then
    io.stderr:write("production model is required\n")
    os.exit(2)
end

local handle = assert(io.open(repo .. "/tiger_sentence.codes.txt", "rb"))
local first_by_code = {}
local order = {}
for line in handle:lines() do
    if line ~= "" and line:sub(1, 1) ~= "#" then
        local text, code = line:match("^(%S+)%s+(%S+)")
        if text and code and not first_by_code[code] then
            first_by_code[code] = text
            order[#order + 1] = code
        end
    end
end
handle:close()

local phrase_cases = {}
local contexts = {
    { prefix = "", suffix = "ot", text_prefix = "", text_suffix = "是" },
    { prefix = "", suffix = "ue", text_prefix = "", text_suffix = "的" },
    { prefix = "tu", suffix = "", text_prefix = "我", text_suffix = "" }
}
for _, code in ipairs(order) do
    local text = first_by_code[code]
    if utf8.len(text) and utf8.len(text) > 1 then
        for _, context in ipairs(contexts) do
            phrase_cases[#phrase_cases + 1] = {
                raw = context.prefix .. code .. context.suffix,
                target = context.text_prefix .. text .. context.text_suffix,
                phrase = text,
                code = code
            }
        end
    end
end

local function run(active_weight)
    sentence.set_decoder_parameters_for_test({
        canonical_code_reward = active_weight,
        lexical_prior_weight = 0,
        canonical_isolation_factor = 1,
        canonical_isolation_min_code_length = 2
    })
    local outputs = {}
    for index, item in ipairs(phrase_cases) do
        sentence.reset_decode_cache()
        local decoded = sentence.decode_full(item.raw, false, "")
        outputs[index] = decoded[1] and decoded[1].text or ""
        if index % 250 == 0 then
            io.stderr:write(string.format("\rweight %.4g: %d/%d", active_weight, index, #phrase_cases))
            io.stderr:flush()
        end
    end
    io.stderr:write("\n")
    return outputs
end

local baseline = run(0)
local changed = weight == 0 and baseline or run(weight)
local baseline_correct, retained, regressed, rescued = 0, 0, 0, 0
local examples = {}
for index, item in ipairs(phrase_cases) do
    local was_correct = baseline[index] == item.target
    local is_correct = changed[index] == item.target
    if was_correct then
        baseline_correct = baseline_correct + 1
        if is_correct then
            retained = retained + 1
        else
            regressed = regressed + 1
            if #examples < 20 then
                examples[#examples + 1] = string.format(
                    "REGRESS\t%s\t%s\t%s\t%s\t%s",
                    item.code, item.phrase, item.raw, item.target, changed[index])
            end
        end
    elseif is_correct then
        rescued = rescued + 1
    end
end

print(string.format(
    "cases=%d weight=%.4g baseline_correct=%d retained=%d regressed=%d rescued=%d",
    #phrase_cases, weight, baseline_correct, retained, regressed, rescued))
for _, example in ipairs(examples) do print(example) end
