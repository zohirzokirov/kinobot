-- Schema dump for database: telegram_bot

-- ----------------------------
-- Table: channels
-- ----------------------------
CREATE TABLE `channels` (
  `id` int NOT NULL AUTO_INCREMENT,
  `channel_link` varchar(255) NOT NULL,
  `channel_username` varchar(255) DEFAULT NULL,
  `channel_id` bigint DEFAULT NULL,
  `is_mandatory` tinyint(1) DEFAULT '1',
  `added_by` bigint DEFAULT NULL,
  `added_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `added_by` (`added_by`),
  CONSTRAINT `channels_ibfk_1` FOREIGN KEY (`added_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table: genres
-- ----------------------------
CREATE TABLE `genres` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table: movie_genres
-- ----------------------------
CREATE TABLE `movie_genres` (
  `movie_id` int NOT NULL,
  `genre_id` int NOT NULL,
  PRIMARY KEY (`movie_id`,`genre_id`),
  KEY `genre_id` (`genre_id`),
  CONSTRAINT `movie_genres_ibfk_1` FOREIGN KEY (`movie_id`) REFERENCES `movies` (`id`) ON DELETE CASCADE,
  CONSTRAINT `movie_genres_ibfk_2` FOREIGN KEY (`genre_id`) REFERENCES `genres` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table: movies
-- ----------------------------
CREATE TABLE `movies` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(255) NOT NULL,
  `quality` varchar(10) NOT NULL,
  `channel_message_id` int DEFAULT NULL,
  `file_id` varchar(255) DEFAULT NULL,
  `added_by` bigint DEFAULT NULL,
  `added_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `added_by` (`added_by`),
  CONSTRAINT `movies_ibfk_1` FOREIGN KEY (`added_by`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ----------------------------
-- Table: users
-- ----------------------------
CREATE TABLE `users` (
  `id` bigint NOT NULL,
  `username` varchar(255) DEFAULT NULL,
  `registered_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

