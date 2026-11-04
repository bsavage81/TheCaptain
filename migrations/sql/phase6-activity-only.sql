-- PREPARED ONLY. Requires separate owner DDL approval and verified backup/recovery.
-- Exactly one new table; intentionally no IF NOT EXISTS, USE, ALTER or DROP.
CREATE TABLE `captain_realm_activity` (
  `id` INTEGER AUTO_INCREMENT NOT NULL PRIMARY KEY,
  `key` VARCHAR(64) NOT NULL,
  `player_id` INTEGER,
  `xuid` VARCHAR(20),
  `realm_id` VARCHAR(20) NOT NULL,
  `source` VARCHAR(32) NOT NULL,
  `raw_start` TEXT NOT NULL,
  `raw_end` TEXT NOT NULL,
  `start` DATETIME,
  `end` DATETIME,
  `status` VARCHAR(32) NOT NULL,
  `reason` VARCHAR(64) NOT NULL,
  `first_observed` DATETIME NOT NULL,
  `last_observed` DATETIME NOT NULL,
  FOREIGN KEY (`player_id`) REFERENCES `captain_player` (`id`),
  UNIQUE KEY `realmactivity_key` (`key`),
  KEY `realmactivity_player_id` (`player_id`),
  KEY `realmactivity_xuid` (`xuid`),
  KEY `realmactivity_realm_id` (`realm_id`),
  KEY `realmactivity_realm_id_xuid_start_end` (`realm_id`, `xuid`, `start`, `end`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
