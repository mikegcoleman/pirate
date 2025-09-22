-- WirePlumber override to keep the Skelly prop on plain SBC with a conservative
-- bitpool. Copy this file to ~/.config/wireplumber/bluetooth.lua.d/60-skelly.lua
-- on the Raspberry Pi and restart WirePlumber.

bluez_monitor = bluez_monitor or {}
bluez_monitor.rules = bluez_monitor.rules or {}

-- Restrict the Skelly card to standard SBC with a mild bitpool range.
table.insert(bluez_monitor.rules, 1, {
  matches = {
    {
      { "device.name", "equals", "bluez_card.24_F4_95_F4_CA_45" },
    },
  },
  apply_properties = {
    ["bluez5.codecs"] = "[ sbc ]",
    ["bluez5.a2dp.sbc-min-bitpool"] = 32,
    ["bluez5.a2dp.sbc-max-bitpool"] = 53,
  },
})

-- Ensure the sink node also inherits the same bitpool caps.
table.insert(bluez_monitor.rules, 1, {
  matches = {
    {
      { "node.name", "equals", "bluez_output.24_F4_95_F4_CA_45.1" },
    },
  },
  apply_properties = {
    ["bluez5.a2dp.sbc-min-bitpool"] = 32,
    ["bluez5.a2dp.sbc-max-bitpool"] = 53,
  },
})
