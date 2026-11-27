-- CET probe of the `ga ingame` harness. Commands come from cmd.txt (re-read when it changes), results go to out.txt.
-- The last line of a command file is `#<token>`; the probe logs `done <token>` when the whole file has run.
--   mark <text>              section line      ready                 logs ready=true when V is attached
--   give <rec> [n]           add items         eq <rec> <slot>       equip (0 right, 3 left)
--   hol                      holster           gs                    guns in hands, dual flag
--   stats <tag>              stats of both guns (WS list)             pstat <Stat...>    player stats
--   mags / refill            magazine counts / refill both guns       god                V immortal
--   tp <x> <y> <z> [yaw]     teleport V        civ <radius>          NPCs near V (unverified API, may log unknown)
--   dummy <dist> [dz]        frozen invulnerable dummy in front of the camera, tagged GAIngame
--   undummy                  delete it         lua <code>            run code (log(...) writes a line)
--   shots <tag>              fires seen by the weapon since the last mark (Observe on WeaponObject)
local out
local function log(s)
  out = out or io.open("out.txt", "a")
  out:write(os.date("%H:%M:%S ") .. s .. "\n"); out:flush()
end
local function recName(id) return TDBID.ToStringDEBUG(ItemID.GetTDBID(id)) end
local function slotItem(s) return Game.GetTransactionSystem():GetItemInSlot(Game.GetPlayer(), TweakDBID.new(s)) end
local function inventory()
  local ok, items = Game.GetTransactionSystem():GetItemList(Game.GetPlayer())
  return ok and items or {}
end
local function wtype(w)
  local r = TweakDB:GetRecord(ItemID.GetTDBID(w:GetItemID()))
  local t, e = "?", "?"
  pcall(function() t = tostring(r:ItemType():Type().value) end)
  pcall(function() e = tostring(r:Evolution():Type().value) end)
  return t, e
end

local WS = {"StaminaCostReduction", "EquipDuration", "UnequipDuration", "CycleTimeBonus", "RecoilKickMin", "RecoilKickMax",
  "HeadshotDamageMultiplier", "WeakspotDamageMultiplier", "ReloadTime", "EmptyReloadTime", "CycleTime"}

local fired = {R = 0, L = 0}
local cmds = {}
function cmds.mark(...) fired = {R = 0, L = 0}; log("---- " .. table.concat({...}, " ")) end
function cmds.lua(...) local f = assert(loadstring("local log = ...; " .. table.concat({...}, " "), "cmd")); f(log) end
function cmds.ready()
  local p = Game.GetPlayer()
  log("ready=" .. tostring(p ~= nil and p:IsAttached()))
end
function cmds.give(rec, n) Game.AddToInventory(rec, tonumber(n or "1")); log("give " .. rec) end
function cmds.eq(rec, s)
  for _, d in ipairs(inventory()) do
    if recName(d:GetID()) == rec and not EquipmentSystem.GetData(Game.GetPlayer()):IsEquipped(d:GetID()) then
      local req = EquipRequest.new()
      req.owner = Game.GetPlayer(); req.itemID = d:GetID(); req.slotIndex = tonumber(s)
      Game.GetScriptableSystemsContainer():Get("EquipmentSystem"):QueueRequest(req)
      log("eq " .. rec .. " -> " .. s); return
    end
  end
  log("eq: no " .. rec)
end
function cmds.hol()
  local r = EquipmentSystemWeaponManipulationRequest.new(); r.owner = Game.GetPlayer()
  r.requestType = EquipmentManipulationAction.UnequipWeapon
  Game.GetScriptableSystemsContainer():Get("EquipmentSystem"):QueueRequest(r); log("holster")
end
function cmds.gs()
  local p = Game.GetPlayer()
  local function slot(s) local it = slotItem(s); return it and recName(it:GetItemID()) or "none" end
  log("gs right=" .. slot("AttachmentSlots.WeaponRight") .. " left=" .. slot("AttachmentSlots.WeaponLeft")
    .. " dual=" .. tostring(GameObject.IsDualWielding(p)))
end
function cmds.stats(tag)
  local ss = Game.GetStatsSystem()
  for _, s in ipairs({"WeaponRight", "WeaponLeft"}) do
    local w = slotItem("AttachmentSlots." .. s)
    if w then
      local t, e = wtype(w)
      local line = "stats " .. tostring(tag) .. " " .. s:sub(7, 7) .. " " .. recName(w:GetItemID()) .. " type=" .. t .. " evo=" .. e
      for _, n in ipairs(WS) do
        local st = gamedataStatType[n]
        if st then line = line .. " " .. n .. "=" .. string.format("%.3f", ss:GetStatValue(w:GetEntityID(), st)) end
      end
      log(line)
    else
      log("stats " .. tostring(tag) .. " " .. s:sub(7, 7) .. " none")
    end
  end
end
function cmds.pstat(...)
  local ss, id, line = Game.GetStatsSystem(), Game.GetPlayer():GetEntityID(), "pstat"
  for _, n in ipairs({...}) do
    local st = gamedataStatType[n]
    line = line .. " " .. n .. "=" .. (st and string.format("%.3f", ss:GetStatValue(id, st)) or "?")
  end
  log(line)
end
function cmds.mags()
  local r, l = slotItem("AttachmentSlots.WeaponRight"), slotItem("AttachmentSlots.WeaponLeft")
  log("mags right=" .. tostring(r and WeaponObject.GetMagazineAmmoCount(r)) .. " left=" .. tostring(l and WeaponObject.GetMagazineAmmoCount(l)))
end
function cmds.refill()
  for _, s in ipairs({"AttachmentSlots.WeaponRight", "AttachmentSlots.WeaponLeft"}) do
    local w = slotItem(s)
    if w then
      local e = SetAmmoCountEvent.new(); e.ammoTypeID = WeaponObject.GetAmmoType(w); e.count = WeaponObject.GetMagazineCapacity(w); w:QueueEvent(e)
    end
  end
  log("refill")
end
function cmds.god()
  local p = Game.GetPlayer(); local id = p:GetEntityID()
  Game.GetStatsSystem():AddModifier(id, RPGManager.CreateStatModifier(gamedataStatType.Health, gameStatModifierType.Additive, 200000))
  Game.GetGodModeSystem():AddGodMode(id, gameGodModeType.Immortal, CName.new("gaingame"))
  log("god ok")
end
function cmds.tp(x, y, z, yaw)
  local p = Game.GetPlayer()
  Game.GetTeleportationFacility():Teleport(p, Vector4.new(tonumber(x), tonumber(y), tonumber(z), 1), EulerAngles.new(0, 0, tonumber(yaw or "0")))
  log("tp " .. x .. " " .. y .. " " .. z)
end
function cmds.civ(r)
  local n = nil
  pcall(function()
    local ts = Game.GetTargetingSystem()
    local q = TSQ_NPC(); q.maxDistance = tonumber(r)
    local ok, parts = ts:GetTargetParts(Game.GetPlayer(), q)
    n = 0
    for _, part in ipairs(parts or {}) do
      local o = part:GetComponent(part):GetEntity()
      if o and o:IsNPC() and not o:IsDead() and o:GetEntityID() ~= GAI_t then n = n + 1 end
    end
  end)
  log("civ radius=" .. tostring(r) .. " n=" .. (n and tostring(n) or "unknown"))
end
function cmds.dummy(dist, dz)
  local ok, err = pcall(function()
    if GAI_t then pcall(function() Game.GetDynamicEntitySystem():DeleteEntity(GAI_t) end); GAI_t = nil end
    local p = Game.GetPlayer(); local pos = p:GetFPPCameraComponent():GetLocalToWorld():GetTranslation()
    local f = Game.GetCameraSystem():GetActiveCameraForward(); local d = tonumber(dist or "4")
    local spec = DynamicEntitySpec.new(); spec.recordID = TweakDBID.new("Character.sts_ep1_12_security_android_dummy")
    spec.position = Vector4.new(pos.x + f.x * d, pos.y + f.y * d, pos.z + f.z * d - 0.95 + tonumber(dz or "0"), 1)
    spec.orientation = EulerAngles.ToQuat(EulerAngles.new(0, 0, 180))
    spec.persistState = false; spec.persistSpawn = false; spec.alwaysSpawned = true; spec.tags = {CName.new("GAIngame")}
    GAI_t = Game.GetDynamicEntitySystem():CreateEntity(spec)
    log("dummy spawned " .. tostring(EntityID.GetHash(GAI_t)))
  end)
  if not ok then log("dummy error " .. tostring(err)) end
end
function cmds.freeze()
  local e = GAI_t and Game.FindEntityByID(GAI_t)
  if not e then log("freeze: no dummy"); return end
  Game.GetGodModeSystem():AddGodMode(GAI_t, gameGodModeType.Invulnerable, CName.new("gaingame"))
  e:SetIndividualTimeDilation(CName.new("gaingame"), 0.001, 3000, CName.new(""), CName.new(""))
  local q, c = e:GetWorldPosition(), Game.GetPlayer():GetWorldPosition()
  log("frozen dist=" .. string.format("%.1f", math.sqrt((q.x - c.x) ^ 2 + (q.y - c.y) ^ 2)))
end
function cmds.undummy()
  if GAI_t then Game.GetDynamicEntitySystem():DeleteEntity(GAI_t); GAI_t = nil; log("dummy deleted") end
end
function cmds.shots(tag) log("shots " .. tostring(tag) .. " R=" .. fired.R .. " L=" .. fired.L) end

registerForEvent("onInit", function()
  log("init")
  pcall(function()
    ObserveAfter("WeaponObject", "OnShoot", function(self)
      local s = "R"
      pcall(function() if self:GetItemID() == slotItem("AttachmentSlots.WeaponLeft"):GetItemID() then s = "L" end end)
      fired[s] = fired[s] + 1
    end)
  end)
end)

local last, t = nil, 0
registerForEvent("onUpdate", function(dt)
  t = t + dt
  if t < 0.25 then return end
  t = 0
  local f = io.open("cmd.txt", "r")
  if not f then return end
  local text = f:read("*a"); f:close()
  if text == last then return end
  last = text
  local token = ""
  for line in text:gmatch("[^\r\n]+") do
    if line:sub(1, 1) == "#" then token = line:sub(2)
    else
      local words = {}
      for w in line:gmatch("%S+") do table.insert(words, w) end
      local fn = cmds[words[1]]
      if fn then
        local ok, err = pcall(fn, table.unpack(words, 2))
        if not ok then log("error " .. line .. ": " .. tostring(err)) end
      end
    end
  end
  log("done " .. token)
end)
