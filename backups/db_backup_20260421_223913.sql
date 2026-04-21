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
  `display_order` int(11) DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_result` (`roll_number`,`year`,`semester`,`subject_code`),
  CONSTRAINT `results_ibfk_1` FOREIGN KEY (`roll_number`) REFERENCES `students` (`roll_number`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=249 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `results`
--

LOCK TABLES `results` WRITE;
/*!40000 ALTER TABLE `results` DISABLE KEYS */;
INSERT INTO `results` VALUES
(211,'2271010',1,1,'20BST04','Engineering Mathematics-1',4,22,41,63,100,7.00,'C','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',0),
(212,'2271010',1,1,'20BST03','Engineering Physics',4,28,41,69,100,7.00,'C','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',1),
(213,'2271010',1,1,'20BST01','Functional English',3,18,42,60,100,7.00,'C','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',2),
(214,'2271010',1,1,'20ECT01','Basic Electronics Engineering',3,24,25,49,100,5.00,'P','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',3),
(215,'2271010',1,1,'20BSP03','Engineering Physics Lab',1,38,57,95,100,10.00,'O','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',4),
(216,'2271010',1,1,'20BSP01','Communicative English Lab',3,30,47,77,100,8.00,'B','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',5),
(217,'2271010',1,1,'20MEP03','Workshop & Manufacturing Practices Lab',2,34,51,85,100,9.00,'A','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',6),
(218,'2271010',1,1,'20ECP01','Basic Electronics Engineering Lab',3,36,56,92,100,10.00,'O','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',7),
(219,'2271010',1,2,'20BST05','Engineering Mathematics-II',4,23,39,62,100,7.00,'C','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',0),
(220,'2271010',1,2,'20BST02','Engineering Chemistry',4,21,26,47,100,5.00,'P','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',1),
(221,'2271010',1,2,'20CST01','Programming for Problem Solving',3,21,33,54,100,6.00,'D','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',2),
(222,'2271010',1,2,'20EET01','Basic Electrical Engineering',3,23,38,61,100,7.00,'C','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',3),
(223,'2271010',1,2,'20BSP02','Engineering Chemistry Lab',3,34,44,78,100,8.00,'B','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',4),
(224,'2271010',1,2,'20CSP01','Programming for Problem Solving Lab',2,28,48,76,100,8.00,'B','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',5),
(225,'2271010',1,2,'20EEP01','Basic Electrical Engineering Lab',1,35,53,88,100,9.00,'A','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',6),
(226,'2271010',1,2,'20MEP01','Engineering Graphics',3,38,56,94,100,10.00,'O','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',7),
(227,'2271010',1,2,'20BST13','Essence of Indian Traditional Knowledge',3,18,62,80,100,0.00,'S','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',8),
(228,'2271010',2,1,'20BST08','Economics & Accountancy',4,15,57,72,100,8.00,'B','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',0),
(229,'2271010',2,1,'20BST16','Universal Human Values & Ethics',3,23,43,66,100,7.00,'C','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',1),
(230,'2271010',2,1,'20ECT26','Digital Logic Design',3,23,53,76,100,8.00,'B','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',2),
(231,'2271010',2,1,'20MET13','Operations Research',4,29,56,85,100,9.00,'A','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',3),
(232,'2271010',2,1,'20CST02','Discrete Mathematics',3,27,39,66,100,7.00,'C','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',4),
(233,'2271010',2,1,'20CST03','Data Structures',3,25,36,61,100,7.00,'C','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',5),
(234,'2271010',2,1,'20ECP12','Digital Logic Design Lab',1,37,56,93,100,10.00,'O','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',6),
(235,'2271010',2,1,'20CSP02','Data Structures Lab',1,31,56,87,100,9.00,'A','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',7),
(236,'2271010',2,1,'20CSP03','IT Workshop',1,35,48,83,100,9.00,'A','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',8),
(237,'2271010',2,1,'20CSS01','Learning Tableau Lab',2,33,45,78,100,8.00,'B','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',9),
(238,'2271010',2,2,'20BST07','Probability &Statistics',3,24,49,73,100,8.00,'B','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',0),
(239,'2271010',2,2,'20BST09','industria Management',3,26,59,85,100,9.00,'A','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',1),
(240,'2271010',2,2,'20CST04','Computer Architecture and Organization',3,18,49,67,100,7.00,'C','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',2),
(241,'2271010',2,2,'20CST05','Object Oriented Programming',3,25,35,60,100,7.00,'C','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',3),
(242,'2271010',2,2,'20CST06','Database Management Systems',3,27,44,71,100,8.00,'B','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',4),
(243,'2271010',2,2,'20CST16','Data Mining',3,24,29,53,100,6.00,'D','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',5),
(244,'2271010',2,2,'20CSP04','Object Oriented Programming Lab',3,36,37,73,100,8.00,'B','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',6),
(245,'2271010',2,2,'20CSP05','Lab Database Management Systems',1,31,41,72,100,8.00,'B','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',7),
(246,'2271010',2,2,'20CSP06','Mathematical Toolkit Lab',1,34,48,82,100,9.00,'A','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',8),
(247,'2271010',2,2,'20CSS02','Skill Oriented Course 2 (PHP-Hypertext Preprocessor Lab) 2',3,23,31,54,100,6.00,'D','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',9),
(248,'2271010',2,2,'20BST12','Environmental Studies',3,26,63,89,100,0.00,'S','PASS',1,'','2026-04-05 12:40:42','2026-04-05 12:40:42',10);
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
) ENGINE=InnoDB AUTO_INCREMENT=33 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `semester_summary`
--

LOCK TABLES `semester_summary` WRITE;
/*!40000 ALTER TABLE `semester_summary` DISABLE KEYS */;
INSERT INTO `semester_summary` VALUES
(29,'2271010',1,1,7.26,590,8,8,0,'','2026-04-05 12:40:42','2026-04-05 12:40:42'),
(30,'2271010',1,2,7.14,640,9,9,0,'','2026-04-05 12:40:42','2026-04-05 12:40:42'),
(31,'2271010',2,1,7.96,767,10,10,0,'','2026-04-05 12:40:42','2026-04-05 12:40:42'),
(32,'2271010',2,2,7.46,779,11,11,0,'','2026-04-05 12:40:42','2026-04-05 12:40:42');
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
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `students`
--

LOCK TABLES `students` WRITE;
/*!40000 ALTER TABLE `students` DISABLE KEYS */;
INSERT INTO `students` VALUES
(8,'gowtham','2271010','CSE','A','scrypt:32768:8:1$AUu3Ka0cE423nYED$f9cb56aec190b1528d9a27c37fa24e26878f7cfc4e3579a36dce40ac990c94561994756949a9337164b5e3cf3bf5c42a36c01b821b2df042a0065b308a9cc111','2026-04-05 12:37:53','2026-04-05 12:37:53');
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
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `upload_history`
--

LOCK TABLES `upload_history` WRITE;
/*!40000 ALTER TABLE `upload_history` DISABLE KEYS */;
INSERT INTO `upload_history` VALUES
(7,'2271010','memo-1.pdf','2026-04-05 12:40:42','[{\"year\": 1, \"semester\": 1, \"subject_codes\": [\"20BST04\", \"20BST03\", \"20BST01\", \"20ECT01\", \"20BSP03\", \"20BSP01\", \"20MEP03\", \"20ECP01\"]}, {\"year\": 1, \"semester\": 2, \"subject_codes\": [\"20BST05\", \"20BST02\", \"20CST01\", \"20EET01\", \"20BSP02\", \"20CSP01\", \"20EEP01\", \"20MEP01\", \"20BST13\"]}, {\"year\": 2, \"semester\": 1, \"subject_codes\": [\"20BST08\", \"20BST16\", \"20ECT26\", \"20MET13\", \"20CST02\", \"20CST03\", \"20ECP12\", \"20CSP02\", \"20CSP03\", \"20CSS01\"]}, {\"year\": 2, \"semester\": 2, \"subject_codes\": [\"20BST07\", \"20BST09\", \"20CST04\", \"20CST05\", \"20CST06\", \"20CST16\", \"20CSP04\", \"20CSP05\", \"20CSP06\", \"20CSS02\", \"20BST12\"]}]',38,4,'CONFIRMED');
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

-- Dump completed on 2026-04-21 17:09:13
