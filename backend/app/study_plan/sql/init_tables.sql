-- 学习规划模块建表脚本（T1.5）
-- 由 SQLAlchemy model 渲染生成；schema = fba
-- 执行前置：study_user_account / sys_user 已存在
-- 表依赖序：template -> plan -> item -> record；mentor_student 独立

BEGIN;

-- ===== study_plan_template =====
CREATE TABLE study_plan_template (
	id BIGSERIAL NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	duration_days INTEGER NOT NULL, 
	domain VARCHAR(32) NOT NULL, 
	description TEXT, 
	is_active BOOLEAN NOT NULL, 
	created_by INTEGER NOT NULL, 
	updated_by INTEGER, 
	created_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_time TIMESTAMP WITH TIME ZONE, 
	deleted BIGINT DEFAULT '0' NOT NULL, 
	deleted_time TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_study_plan_template_duration CHECK (duration_days > 0)
);
CREATE INDEX idx_study_plan_template_creator ON study_plan_template (created_by);
CREATE INDEX idx_study_plan_template_domain_active ON study_plan_template (domain, is_active);
CREATE UNIQUE INDEX ix_study_plan_template_id ON study_plan_template (id);

-- ===== study_plan_template_item =====
CREATE TABLE study_plan_template_item (
	id BIGSERIAL NOT NULL, 
	template_id BIGINT NOT NULL, 
	day_index INTEGER NOT NULL, 
	order_index INTEGER NOT NULL, 
	module_type VARCHAR(16) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	ref_type VARCHAR(32) NOT NULL, 
	ref_id BIGINT, 
	expected_minutes INTEGER NOT NULL, 
	extra JSONB, 
	created_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_time TIMESTAMP WITH TIME ZONE, 
	deleted BIGINT DEFAULT '0' NOT NULL, 
	deleted_time TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_study_plan_template_item_position UNIQUE (template_id, day_index, order_index), 
	CONSTRAINT ck_study_plan_template_item_module_type CHECK (module_type IN ('review','practice','wrong_review','ability')), 
	CONSTRAINT ck_study_plan_template_item_ref_type CHECK (ref_type IN ('content','question_set','wrong_dynamic','ability_task')), 
	CONSTRAINT ck_study_plan_template_item_day CHECK (day_index > 0), 
	CONSTRAINT ck_study_plan_template_item_order CHECK (order_index >= 0), 
	CONSTRAINT ck_study_plan_template_item_minutes CHECK (expected_minutes >= 0), 
	FOREIGN KEY(template_id) REFERENCES study_plan_template (id) ON DELETE CASCADE
);
CREATE INDEX idx_study_plan_template_item_template_day ON study_plan_template_item (template_id, day_index, order_index);
CREATE UNIQUE INDEX ix_study_plan_template_item_id ON study_plan_template_item (id);

-- ===== study_plan =====
CREATE TABLE study_plan (
	id BIGSERIAL NOT NULL, 
	user_id BIGINT NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	domain VARCHAR(32) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	template_id BIGINT, 
	created_by INTEGER NOT NULL, 
	updated_by INTEGER, 
	created_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_time TIMESTAMP WITH TIME ZONE, 
	deleted BIGINT DEFAULT '0' NOT NULL, 
	deleted_time TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_study_plan_status CHECK (status IN ('active','paused','finished')), 
	CONSTRAINT ck_study_plan_dates CHECK (end_date >= start_date), 
	FOREIGN KEY(user_id) REFERENCES study_user_account (user_id) ON DELETE CASCADE, 
	FOREIGN KEY(template_id) REFERENCES study_plan_template (id) ON DELETE SET NULL
);
CREATE INDEX idx_study_plan_template ON study_plan (template_id) WHERE template_id IS NOT NULL;
CREATE INDEX idx_study_plan_user_dates ON study_plan (user_id, start_date, end_date);
CREATE UNIQUE INDEX ix_study_plan_id ON study_plan (id);
CREATE INDEX idx_study_plan_user_status ON study_plan (user_id, status);

-- ===== study_plan_item =====
CREATE TABLE study_plan_item (
	id BIGSERIAL NOT NULL, 
	plan_id BIGINT NOT NULL, 
	user_id BIGINT NOT NULL, 
	plan_date DATE NOT NULL, 
	order_index INTEGER NOT NULL, 
	module_type VARCHAR(16) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	ref_type VARCHAR(32) NOT NULL, 
	ref_id BIGINT, 
	expected_minutes INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	extra JSONB, 
	created_by INTEGER NOT NULL, 
	updated_by INTEGER, 
	created_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_time TIMESTAMP WITH TIME ZONE, 
	deleted BIGINT DEFAULT '0' NOT NULL, 
	deleted_time TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_study_plan_item_module_type CHECK (module_type IN ('review','practice','wrong_review','ability')), 
	CONSTRAINT ck_study_plan_item_ref_type CHECK (ref_type IN ('content','question_set','wrong_dynamic','ability_task')), 
	CONSTRAINT ck_study_plan_item_status CHECK (status IN ('pending','in_progress','completed','skipped')), 
	CONSTRAINT ck_study_plan_item_order CHECK (order_index >= 0), 
	CONSTRAINT ck_study_plan_item_minutes CHECK (expected_minutes >= 0), 
	FOREIGN KEY(plan_id) REFERENCES study_plan (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES study_user_account (user_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX ix_study_plan_item_id ON study_plan_item (id);
CREATE INDEX idx_study_plan_item_plan_date_order ON study_plan_item (plan_id, plan_date, order_index);
CREATE INDEX idx_study_plan_item_user_date_status ON study_plan_item (user_id, plan_date, status);
CREATE INDEX idx_study_plan_item_ref ON study_plan_item (ref_type, ref_id) WHERE ref_id IS NOT NULL;

-- ===== study_plan_record =====
CREATE TABLE study_plan_record (
	id BIGSERIAL NOT NULL, 
	item_id BIGINT NOT NULL, 
	user_id BIGINT NOT NULL, 
	duration_seconds INTEGER NOT NULL, 
	score INTEGER, 
	correct_count INTEGER, 
	total_count INTEGER, 
	extra_data JSONB, 
	completed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_time TIMESTAMP WITH TIME ZONE, 
	deleted BIGINT DEFAULT '0' NOT NULL, 
	deleted_time TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_study_plan_record_duration CHECK (duration_seconds >= 0), 
	CONSTRAINT ck_study_plan_record_counts CHECK ((correct_count IS NULL OR correct_count >= 0) AND (total_count IS NULL OR total_count >= 0) AND (correct_count IS NULL OR total_count IS NULL OR correct_count <= total_count)), 
	CONSTRAINT ck_study_plan_record_score CHECK (score IS NULL OR score >= 0), 
	FOREIGN KEY(item_id) REFERENCES study_plan_item (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES study_user_account (user_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX ix_study_plan_record_id ON study_plan_record (id);
CREATE INDEX idx_study_plan_record_user_time ON study_plan_record (user_id, completed_at);
CREATE INDEX idx_study_plan_record_item ON study_plan_record (item_id);

-- ===== study_mentor_student =====
CREATE TABLE study_mentor_student (
	id BIGSERIAL NOT NULL, 
	mentor_id BIGINT NOT NULL, 
	student_id BIGINT NOT NULL, 
	assigned_by BIGINT, 
	status VARCHAR(16) NOT NULL, 
	note VARCHAR(255), 
	assigned_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	created_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_time TIMESTAMP WITH TIME ZONE, 
	deleted BIGINT DEFAULT '0' NOT NULL, 
	deleted_time TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_study_mentor_student_pair UNIQUE (mentor_id, student_id), 
	CONSTRAINT ck_study_mentor_student_not_self CHECK (mentor_id <> student_id), 
	CONSTRAINT ck_study_mentor_student_status CHECK (status IN ('active','paused')), 
	FOREIGN KEY(mentor_id) REFERENCES study_user_account (user_id) ON DELETE CASCADE, 
	FOREIGN KEY(student_id) REFERENCES study_user_account (user_id) ON DELETE CASCADE, 
	FOREIGN KEY(assigned_by) REFERENCES sys_user (id) ON DELETE SET NULL
);
CREATE INDEX idx_study_mentor_student_mentor ON study_mentor_student (mentor_id, status);
CREATE UNIQUE INDEX ix_study_mentor_student_id ON study_mentor_student (id);
CREATE INDEX idx_study_mentor_student_student ON study_mentor_student (student_id, status);

COMMIT;