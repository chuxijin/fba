-- 资源表 is_temp_file 字段由布尔改为枚举整型(0/1/2/3)
-- 0 无操作
-- 1 定时删除
-- 2 定时刷新
-- 3 定时更新

ALTER TABLE "yp_resource"
  ALTER COLUMN "is_temp_file" TYPE SMALLINT USING CASE WHEN "is_temp_file"=true THEN 1 WHEN "is_temp_file"=false THEN 0 ELSE 0 END,
  ALTER COLUMN "is_temp_file" SET DEFAULT 0;

COMMENT ON COLUMN "yp_resource"."is_temp_file" IS '临时处理模式(0无操作 1定时删除 2定时刷新 3定时更新)';


