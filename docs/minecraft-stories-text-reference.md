# Minecraft Stories event text reference

Source: installed Minecraft for Windows `Content/data/resource_packs/oreui/texts/en_US.lang`.

These are localization templates, not evidence of the live API payload fields. `%1$s` and `%2$s` are positional substitutions. Their meanings vary by event; do not assume every placeholder is a player.

| Event | Variant | English template |
|---|---|---|
| `FirstEnderDragonDefeated` | large | The Ender Dragon was defeated! |
| `FirstWitherDefeated` | large | The Wither was defeated! |
| `250HostileMobs` | medium | %1$s cannot be defeated by mere mobs |
| `250HostileMobs` | medium / grouped | %1$s cannot be defeated by mere mobs |
| `AllMobNameEasterEggs` | medium | %1$s created all the mystery mobs |
| `AllMobNameEasterEggs` | medium / grouped | %1$s created all the mystery mobs |
| `CookEverything` | medium | %1$s prepared a 13 course meal |
| `DefeatEnderdragon` | medium | %1$s defeated the Ender Dragon!... again |
| `DefeatEnderdragon` | medium / grouped | The Ender Dragon was defeated!... again |
| `DefeatWither` | medium | %1$s defeated the Wither!... again |
| `DefeatWither` | medium / grouped | The Wither was defeated!... again |
| `DiamondEverything` | medium | %1$s has a full diamond set |
| `DiamondEverything` | medium / grouped | %1$s have full diamond sets |
| `FirstAbandonedMineshaftFound` | medium | %1$s discovered an Abandoned Mineshaft |
| `FirstAncientCityFound` | medium | %1$s discovered an Ancient City |
| `FirstBadlandsFound` | medium | %1$s discovered a Badlands |
| `FirstConduit` | medium | %1$s now commands the sea |
| `FirstCraftedNetherite` | medium | %1$s upgraded to Netherite |
| `FirstCraftedNetherite` | medium / grouped | %1$s upgraded to Netherite |
| `FirstDiamondFound` | medium | %1$s found a diamond |
| `FirstEnchantment` | medium | %1$s discovered enchanting |
| `FirstEnchantment` | medium / grouped | %1$s discovered enchanting |
| `FirstEndPortal` | medium | %1$s traveled to the End? |
| `FirstFullyExploredMap` | medium | %1$s started mapping the world |
| `FirstMushroomFieldFound` | medium | %1$s discovered a Mushroom Field |
| `FirstNetherFortressFound` | medium | %1$s discovered a Nether Fortress |
| `FirstNetherPortalLit` | medium | %1$s created a portal to the Nether |
| `FirstPeakMountainFound` | medium | %1$s scaled a Mountain Peak |
| `FirstPillagerOutpostFound` | medium | %1$s discovered a Pillager Outpost |
| `FirstPoweredBeacon` | medium | %1$s powered a Beacon! |
| `FirstWoodlandMansionFound` | medium | %1$s discovered a Woodland Mansion |
| `NamedMob` | medium | %1$s has a new friend, %2$s |
| `NamedMobDies` | medium | %1$s met an untimely death |
| `NewMember` | medium | %1$s joined the Realm |
| `NewMember` | medium / grouped | %1$s joined the Realm |
| `PillagerCaptainDefeated` | medium | %1$s defeated a Pillager Captain |
| `RealmCreated` | medium | A new adventure has begun! What will the story of this Realm be? You decide. |
| `SlotSwitch` | medium | The world changed to %1$s |

`EasyAndSafe` has artwork but no matching medium/large event template in this file.

Grouped boss rematches use impersonal text. `NamedMob` needs two substitutions; `NamedMobDies` refers to the named mob, and `SlotSwitch` takes a world name. Verify payload fields before mapping these values.
