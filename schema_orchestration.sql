-- botMaster v2.0 Orchestration Schema
-- Database: task_log_db (existing, shared with task management agent)
-- Purpose: Track agent sessions, messages, and decisions for work project orchestration

USE task_log_db;

-- Agent Sessions: Track which agents are running for which projects
CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    tool_name ENUM('claude-flow', 'gemini', 'cursor-agent', 'nested-claude') NOT NULL,
    project_path VARCHAR(500),
    project_name VARCHAR(255),
    status ENUM('running', 'waiting', 'completed', 'failed', 'crashed') DEFAULT 'running',
    pid INT,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    current_task TEXT,
    output_log LONGTEXT,
    exit_code INT NULL,
    error_message TEXT NULL,
    INDEX idx_status (status),
    INDEX idx_tool (tool_name),
    INDEX idx_project (project_name),
    INDEX idx_started (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Agent Messages: Cross-agent communication and message queue
CREATE TABLE IF NOT EXISTS agent_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    from_agent VARCHAR(255),
    to_agent VARCHAR(255),
    message_type ENUM('request', 'response', 'notification', 'error') DEFAULT 'request',
    message TEXT NOT NULL,
    context_data JSON,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending', 'processing', 'done', 'error') DEFAULT 'pending',
    processed_at DATETIME NULL,
    response TEXT NULL,
    INDEX idx_status (status),
    INDEX idx_to_agent (to_agent),
    INDEX idx_timestamp (timestamp),
    FOREIGN KEY (from_agent) REFERENCES agent_sessions(session_id) ON DELETE SET NULL,
    FOREIGN KEY (to_agent) REFERENCES agent_sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Orchestration Decisions: Log important decisions made during orchestration
CREATE TABLE IF NOT EXISTS orchestration_decisions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project VARCHAR(255),
    decision_type ENUM('tool_selection', 'agent_spawn', 'task_delegation', 'error_handling', 'other') DEFAULT 'other',
    decision TEXT NOT NULL,
    reasoning TEXT,
    alternatives_considered JSON,
    outcome ENUM('success', 'partial', 'failed', 'pending') DEFAULT 'pending',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    markus_feedback TEXT NULL,
    feedback_timestamp DATETIME NULL,
    INDEX idx_project (project),
    INDEX idx_decision_type (decision_type),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Create view for active agents (convenient query)
CREATE OR REPLACE VIEW active_agents AS
SELECT
    session_id,
    tool_name,
    project_name,
    current_task,
    TIMESTAMPDIFF(SECOND, started_at, NOW()) AS uptime_seconds,
    last_activity
FROM agent_sessions
WHERE status = 'running'
ORDER BY started_at DESC;

-- Create view for pending messages (message queue)
CREATE OR REPLACE VIEW pending_messages AS
SELECT
    id,
    to_agent,
    message_type,
    message,
    timestamp,
    TIMESTAMPDIFF(SECOND, timestamp, NOW()) AS age_seconds
FROM agent_messages
WHERE status = 'pending'
ORDER BY timestamp ASC;

-- Grant permissions (assuming mcp_admin user exists)
GRANT SELECT, INSERT, UPDATE, DELETE ON task_log_db.agent_sessions TO 'mcp_admin'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON task_log_db.agent_messages TO 'mcp_admin'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON task_log_db.orchestration_decisions TO 'mcp_admin'@'%';
GRANT SELECT ON task_log_db.active_agents TO 'mcp_admin'@'%';
GRANT SELECT ON task_log_db.pending_messages TO 'mcp_admin'@'%';
FLUSH PRIVILEGES;
