-- PostgreSQL 触发器：自动记录资源浏览量历史
-- 当 yp_resource 表的 view_count 字段更新时，自动在 resource_view_history 表中插入记录

-- 创建触发器函数：资源浏览量更新时自动记录历史
CREATE OR REPLACE FUNCTION fn_resource_view_count_update()
RETURNS TRIGGER AS $$
BEGIN
    -- 只有当 view_count 字段发生变化且 pwd_id 不为空时才记录
    IF OLD.view_count != NEW.view_count AND NEW.pwd_id IS NOT NULL AND NEW.pwd_id != '' THEN
        INSERT INTO resource_view_history (pwd_id, view_count, record_time)
        VALUES (NEW.pwd_id, NEW.view_count, NOW());
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器：资源浏览量更新时自动记录历史
CREATE TRIGGER tr_resource_view_count_update
    AFTER UPDATE ON yp_resource
    FOR EACH ROW
    EXECUTE FUNCTION fn_resource_view_count_update();

-- 创建触发器函数：资源插入时如果有浏览量也记录历史（可选）
CREATE OR REPLACE FUNCTION fn_resource_view_count_insert()
RETURNS TRIGGER AS $$
BEGIN
    -- 如果新插入的记录有浏览量且 pwd_id 不为空，则记录初始状态
    IF NEW.view_count > 0 AND NEW.pwd_id IS NOT NULL AND NEW.pwd_id != '' THEN
        INSERT INTO resource_view_history (pwd_id, view_count, record_time)
        VALUES (NEW.pwd_id, NEW.view_count, NOW());
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 创建触发器：资源插入时如果有浏览量也记录历史
CREATE TRIGGER tr_resource_view_count_insert
    AFTER INSERT ON yp_resource
    FOR EACH ROW
    EXECUTE FUNCTION fn_resource_view_count_insert();

-- 查看触发器
-- SELECT trigger_name, event_manipulation, event_object_table 
-- FROM information_schema.triggers 
-- WHERE event_object_table = 'yp_resource';

-- 删除触发器（如果需要）
-- DROP TRIGGER IF EXISTS tr_resource_view_count_update ON yp_resource;
-- DROP TRIGGER IF EXISTS tr_resource_view_count_insert ON yp_resource;
-- DROP FUNCTION IF EXISTS fn_resource_view_count_update();
-- DROP FUNCTION IF EXISTS fn_resource_view_count_insert(); 