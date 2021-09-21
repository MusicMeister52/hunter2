-- Copyright (C) 2018 The Hunter2 Contributors.
--
-- This file is part of Hunter2.
--
-- Hunter2 is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free
-- Software Foundation, either version 3 of the License, or (at your option) any later version.
--
-- Hunter2 is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
-- PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
--
-- You should have received a copy of the GNU Affero General Public License along with Hunter2.  If not, see <http://www.gnu.org/licenses/>.


local sandbox = {}

-- Allowed sandbox modules
sandbox.allowed_modules = {
  "cjson",
  "imlib2",
}

-- Sandbox library functions
sandbox.lib = {}

-- Prevents access to the strings metatable
function sandbox.lib.getmetatable(object)
  if object == "" then _G.error("getmetatable can not be used to retrieve the strings metatable") end
  return _G.getmetatable(object)
end

-- Prevents access to the strings metatable
function sandbox.lib.setmetatable(table, metatable)
  if object == "" then _G.error("getmetatable can not be used to retrieve the strings metatable") end
  return _G.setmetatable(table, metatable)
end

-- Prevents direct access to the stdout
function sandbox.lib.print(...)
  -- TODO: Log to the internal state of the sandbox for recovery
end

-- Restrict to allowed modules
function sandbox.lib.require(modname)
  for _, module in ipairs(sandbox.allowed_modules) do
    if module == modname then
      return require(modname)
    end
  end
  error("Requested module '"..modname.."' which is not whitelisted ERROR_SANDBOX_VIOLATION")
end

-- Main library functions import
-- Safe functions taken from http://lua-users.org/wiki/SandBoxes
-- Updated to include functions from Lua 5.3
sandbox.env = {
  _VERSION     = _G._VERSION,

  assert       = _G.assert,
  -- collectgarbage
  -- dofile
  error        = _G.error,
  getmetatable = sandbox.lib.getmetatable,
  ipairs       = _G.ipairs,
  -- load
  -- loadfile
  next         = _G.next,
  pairs        = _G.pairs,
  pcall        = _G.pcall,
  print        = sandbox.lib.print,
  rawequal     = _G.rawequal,
  rawget       = _G.rawget,
  rawlen       = _G.rawlen,
  rawset       = _G.rawset,
  require      = sandbox.lib.require,
  select       = _G.select,
  setmetatable = sandbox.lib.setmetatable,
  tonumber     = _G.tonumber,
  tostring     = _G.tostring,
  type         = _G.type,
  xpcall       = _G.xpcall,

  -- coroutine = {}
  -- debug = {}
  -- io = {} -- TODO: Implement in restricted sandbox

  math = {
    abs        = _G.math.abs,
    acos       = _G.math.acos,
    asin       = _G.math.asin,
    atan       = _G.math.atan,
    atan2      = _G.math.atan2,
    ceil       = _G.math.ceil,
    cos        = _G.math.cos,
    cosh       = _G.math.cosh,
    deg        = _G.math.deg,
    exp        = _G.math.exp,
    floor      = _G.math.floor,
    fmod       = _G.math.fmod,
    frexp      = _G.math.frexp,
    huge       = _G.math.huge,
    ldexp      = _G.math.ldexp,
    log        = _G.math.log,
    max        = _G.math.max,
    min        = _G.math.min,
    modf       = _G.math.modf,
    pi         = _G.math.pi,
    pow        = _G.math.pow,
    rad        = _G.math.rad,
    random     = _G.math.random,
    randomseed = _G.math.randomseed, -- TODO: Seed initial values
    sin        = _G.math.sin,
    sinh       = _G.math.sinh,
    sqrt       = _G.math.sqrt,
    tan        = _G.math.tan,
    tanh       = _G.math.tanh,
  },

  os = {
    clock     = _G.os.clock,
    -- date      = _G.os.date -- TODO: Replace with a safer version
    difftime  = _G.os.difftime,
    -- execute   = _G.os.execute,
    -- exit      = _G.os.exit,
    -- getenv    = _G.os.getenv,
    -- remove    = _G.os.remove,
    -- rename    = _G.os.rename,
    -- setlocale = _G.os.setlocale,
    time      = _G.os.time,
    -- tmpname   = _G.os.tmpname,
  },

  -- package = {}

  string = {
    byte    = _G.string.byte,
    char    = _G.string.char,
    -- dump    = _G.string.dump,
    find    = _G.string.find,
    format  = _G.string.format,
    gmatch  = _G.string.gmatch,
    gdub    = _G.string.gsub,
    len     = _G.string.len,
    lower   = _G.string.lower,
    match   = _G.string.match,
    rep     = _G.string.rep,
    reverse = _G.string.reverse,
    sub     = _G.string.sub,
    upper   = _G.string.upper,
  },

  table = {
    concat = _G.table.concat,
    insert = _G.table.insert,
    pack   = _G.table.pack,
    remove = _G.table.remove,
    sort   = _G.table.sort,
    unpack = _G.table.unpack,
  },
}

function sandbox.enable_limits(instruction_limit, memory_limit)
  sandbox.cpu_count = 0
  debug.sethook(function()
    sandbox.cpu_count = sandbox.cpu_count + 1
    local kilobytes, _ = collectgarbage('count')
    if kilobytes > memory_limit then error("ERROR_MEMORY_LIMIT_EXCEEDED") end
    if sandbox.cpu_count > instruction_limit then error("ERROR_INSTRUCTION_LIMIT_EXCEEDED") end
  end, '', 10)
end

function sandbox.run(sandboxed_code, mem_limit, instruction_limit)
  -- Replace string metatable with sandboxed version
  local metatable = {__index={}}
  for k, v in pairs(sandbox.env.string) do
    metatable['__index'][k] = v
  end
  debug.setmetatable('', metatable)

  -- Disable metatables on primative types
  debug.setmetatable(1, nil)
  debug.setmetatable(function() end, nil)
  debug.setmetatable(true, nil)

  local sandboxed_function, message = load(sandboxed_code, nil, 't', sandbox.env)
  if not sandboxed_function then return nil, message end
  return pcall(sandboxed_function)
end

return sandbox
