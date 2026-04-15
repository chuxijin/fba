DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM sys_menu
        WHERE name = 'PluginRenderBook'
    ) THEN
        INSERT INTO sys_menu (
            title,
            name,
            path,
            sort,
            icon,
            type,
            component,
            perms,
            status,
            display,
            cache,
            link,
            remark,
            parent_id,
            created_time,
            updated_time
        )
        VALUES (
            '题本模板预览',
            'PluginRenderBook',
            '/plugins/render-book',
            90,
            'carbon:book',
            1,
            '/plugins/render_book/views/index',
            NULL,
            1,
            1,
            1,
            '',
            '题本渲染模板预览与参数调试页面',
            (SELECT id FROM sys_menu WHERE name = 'System' LIMIT 1),
            NOW(),
            NULL
        );
    END IF;
END $$;
