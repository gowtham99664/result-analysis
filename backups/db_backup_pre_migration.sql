/*M!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.19  Distrib 10.11.16-MariaDB, for debian-linux-gnu (x86_64)
--
-- Host: localhost    Database: result_analysis
-- ------------------------------------------------------
-- Server version	10.11.16-MariaDB-ubu2204

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `admins`
--

DROP TABLE IF EXISTS `admins`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `admins` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password` varchar(255) NOT NULL,
  `full_name` varchar(255) DEFAULT '',
  `role` enum('super_admin','admin','staff') DEFAULT 'admin',
  `permissions` text DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `admins`
--

LOCK TABLES `admins` WRITE;
/*!40000 ALTER TABLE `admins` DISABLE KEYS */;
INSERT INTO `admins` VALUES
(1,'admin','scrypt:32768:8:1$df98XIA6a0EZNOY3$e5a6b4fb3131b50b32b9d99926f229204ef5684ddc75f57ac6aba189866d582f189abfb4dc6c3ad0a73dd9727b703d64726c394eb54cdc26ba9b440ec567717e','','super_admin',NULL,'2026-04-03 15:53:16');
/*!40000 ALTER TABLE `admins` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `correction_requests`
--

DROP TABLE IF EXISTS `correction_requests`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `correction_requests` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `roll_number` varchar(50) NOT NULL,
  `result_id` int(11) DEFAULT NULL,
  `year` int(11) DEFAULT NULL,
  `semester` int(11) DEFAULT NULL,
  `title` varchar(255) NOT NULL,
  `description` text NOT NULL,
  `attachment_path` varchar(500) DEFAULT NULL,
  `status` enum('PENDING','IN_PROGRESS','REVIEWED','RESOLVED','REJECTED') DEFAULT 'PENDING',
  `admin_remarks` text DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `student_read` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `roll_number` (`roll_number`),
  KEY `result_id` (`result_id`),
  CONSTRAINT `correction_requests_ibfk_1` FOREIGN KEY (`roll_number`) REFERENCES `students` (`roll_number`) ON DELETE CASCADE,
  CONSTRAINT `correction_requests_ibfk_2` FOREIGN KEY (`result_id`) REFERENCES `results` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `correction_requests`
--

LOCK TABLES `correction_requests` WRITE;
/*!40000 ALTER TABLE `correction_requests` DISABLE KEYS */;
/*!40000 ALTER TABLE `correction_requests` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `results`
--

DROP TABLE IF EXISTS `results`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `results` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `roll_number` varchar(50) NOT NULL,
  `year` int(11) NOT NULL,
  `semester` int(11) NOT NULL,
  `subject_code` varchar(50) NOT NULL,
  `subject_name` varchar(255) NOT NULL,
  `credits` int(11) DEFAULT 3,
  `internal_marks` int(11) DEFAULT 0,
  `external_marks` int(11) DEFAULT 0,
  `total_marks` int(11) DEFAULT 0,
  `max_marks` int(11) NOT NULL DEFAULT 100,
  `grade_points` decimal(4,2) DEFAULT 0.00,
  `grade` varchar(5) DEFAULT '',
  `status` enum('PASS','FAIL','AB','MP') DEFAULT 'PASS',
  `attempts` int(11) DEFAULT 1,
  `academic_year` varchar(20) NOT NULL DEFAULT '',
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_result` (`roll_number`,`year`,`semester`,`subject_code`),
  CONSTRAINT `results_ibfk_1` FOREIGN KEY (`roll_number`) REFERENCES `students` (`roll_number`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=211 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `results`
--

LOCK TABLES `results` WRITE;
/*!40000 ALTER TABLE `results` DISABLE KEYS */;
/*!40000 ALTER TABLE `results` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `semester_summary`
--

DROP TABLE IF EXISTS `semester_summary`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `semester_summary` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `roll_number` varchar(50) NOT NULL,
  `year` int(11) NOT NULL,
  `semester` int(11) NOT NULL,
  `sgpa` decimal(4,2) DEFAULT 0.00,
  `total_marks` int(11) DEFAULT 0,
  `total_subjects` int(11) DEFAULT 0,
  `passed_subjects` int(11) DEFAULT 0,
  `failed_subjects` int(11) DEFAULT 0,
  `academic_year` varchar(20) NOT NULL DEFAULT '',
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_semester` (`roll_number`,`year`,`semester`),
  CONSTRAINT `semester_summary_ibfk_1` FOREIGN KEY (`roll_number`) REFERENCES `students` (`roll_number`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=29 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `semester_summary`
--

LOCK TABLES `semester_summary` WRITE;
/*!40000 ALTER TABLE `semester_summary` DISABLE KEYS */;
/*!40000 ALTER TABLE `semester_summary` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `students`
--

DROP TABLE IF EXISTS `students`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `students` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `full_name` varchar(255) NOT NULL,
  `roll_number` varchar(50) NOT NULL,
  `branch` enum('CSE','ECE','EEE','MECH') NOT NULL,
  `section` enum('A','B','C') NOT NULL,
  `password` varchar(255) NOT NULL,
  `created_at` timestamp NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `roll_number` (`roll_number`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `students`
--

LOCK TABLES `students` WRITE;
/*!40000 ALTER TABLE `students` DISABLE KEYS */;
/*!40000 ALTER TABLE `students` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `upload_history`
--

DROP TABLE IF EXISTS `upload_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `upload_history` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `roll_number` varchar(50) NOT NULL,
  `original_filename` varchar(255) NOT NULL DEFAULT '',
  `upload_time` timestamp NULL DEFAULT current_timestamp(),
  `year_semester_data` text DEFAULT NULL,
  `num_subjects` int(11) DEFAULT 0,
  `num_semesters` int(11) DEFAULT 0,
  `status` enum('CONFIRMED','DELETED') DEFAULT 'CONFIRMED',
  PRIMARY KEY (`id`),
  KEY `roll_number` (`roll_number`),
  CONSTRAINT `upload_history_ibfk_1` FOREIGN KEY (`roll_number`) REFERENCES `students` (`roll_number`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `upload_history`
--

LOCK TABLES `upload_history` WRITE;
/*!40000 ALTER TABLE `upload_history` DISABLE KEYS */;
/*!40000 ALTER TABLE `upload_history` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-04-05  2:13:51
