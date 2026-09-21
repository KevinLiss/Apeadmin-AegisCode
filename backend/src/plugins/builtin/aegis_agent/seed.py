"""AegisCode Agent 菜单注册。

菜单结构:
- AegisCode (顶级目录)
  - Agent 运行 (菜单)
    - 查看运行列表 (按钮)
    - 创建运行 (按钮)
    - 控制运行 (按钮)
  - 用量统计 (菜单)
    - 查看用量 (按钮)
  - 运行详情 (菜单，隐藏路由)
"""

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Menu, Role
from src.models.rbac import role_menu


async def seed_aegis_agent_data(db: AsyncSession) -> None:
    """Seed 菜单 + 权限 + 绑定 admin 角色。幂等。"""

    # ── 1. 创建顶级目录 ──────────────────────────────────
    result = await db.execute(
        select(Menu).where(Menu.path == "/aegis-agent", Menu.parent_id == 0)
    )
    parent = result.scalars().first()

    if not parent:
        parent = Menu(
            name="AegisCode",
            parent_id=0,
            type="M",
            path="/aegis-agent",
            component=None,
            permission=None,
            icon="Monitor",
            sort=10,
            visible=1,
            status=1,
        )
        db.add(parent)
        await db.flush()
        logger.info("Created 'AegisCode' top-level menu")

    # ── 2. 子菜单 + 按钮权限 ──────────────────────────────
    # (name, parent_name, type, path, component, permission, icon, sort, visible)
    menu_specs = [
        ("Agent 运行", "AegisCode", "C", "runs", "aegis_agent/runs/index", "aegis_agent:runs:list", "VideoPlay", 1, 1),
        ("创建运行", "Agent 运行", "F", None, None, "aegis_agent:runs:create", None, 1, 1),
        ("控制运行", "Agent 运行", "F", None, None, "aegis_agent:runs:control", None, 2, 1),
        ("删除运行", "Agent 运行", "F", None, None, "aegis_agent:runs:delete", None, 3, 1),
        ("用量统计", "AegisCode", "C", "usage", "aegis_agent/usage/index", "aegis_agent:usage:list", "DataLine", 2, 1),
        # 安全中心
        ("安全中心", "AegisCode", "C", "security", "aegis_agent/security/index", "aegis_security:token-stats", "Lock", 3, 1),
        ("查看调用日志", "安全中心", "F", None, None, "aegis_security:call-logs", None, 1, 1),
        ("查看操作日志", "安全中心", "F", None, None, "aegis_security:action-logs", None, 2, 1),
        ("管理脱敏规则", "安全中心", "F", None, None, "aegis_security:sanitize-rules", None, 3, 1),
        # 预算策略
        ("预算策略", "AegisCode", "C", "budget", "aegis_agent/budget/index", "aegis_budget:list", "Wallet", 5, 1),
        ("创建策略", "预算策略", "F", None, None, "aegis_budget:add", None, 1, 1),
        ("编辑策略", "预算策略", "F", None, None, "aegis_budget:edit", None, 2, 1),
        ("删除策略", "预算策略", "F", None, None, "aegis_budget:delete", None, 3, 1),
        # 技能中心
        ("技能中心", "AegisCode", "C", "skills", "aegis_agent/skills/index", "aegis_skill:list", "MagicStick", 6, 1),
        ("创建技能", "技能中心", "F", None, None, "aegis_skill:add", None, 1, 1),
        ("编辑技能", "技能中心", "F", None, None, "aegis_skill:edit", None, 2, 1),
        ("删除技能", "技能中心", "F", None, None, "aegis_skill:delete", None, 3, 1),
        # MCP 服务器管理
        ("MCP 服务器", "AegisCode", "C", "mcp", "aegis_agent/mcp/index", "aegis_mcp:list", "Link", 7, 1),
        ("创建服务器", "MCP 服务器", "F", None, None, "aegis_mcp:add", None, 1, 1),
        ("编辑服务器", "MCP 服务器", "F", None, None, "aegis_mcp:edit", None, 2, 1),
        ("删除服务器", "MCP 服务器", "F", None, None, "aegis_mcp:delete", None, 3, 1),
        # 运行详情为隐藏路由页（visible=0: 不出现在侧边栏，但动态路由正常注册）
        ("运行详情", "AegisCode", "C", "runs/:id", "aegis_agent/runs/detail", "aegis_agent:runs:detail", "View", 4, 0),
    ]

    existing = list((await db.execute(select(Menu))).scalars().all())
    created_menus: list[Menu] = []

    for name, parent_name, mtype, path, component, permission, icon, sort, visible in menu_specs:
        parent_menu = next((m for m in existing + created_menus if m.name == parent_name), None)
        if not parent_menu:
            logger.warning(f"Skip menu '{name}': parent '{parent_name}' not found")
            continue

        dup = any(m.name == name and m.parent_id == parent_menu.id for m in existing)
        if dup:
            continue

        menu = Menu(
            name=name,
            parent_id=parent_menu.id,
            type=mtype,
            path=path,
            component=component,
            permission=permission,
            icon=icon,
            sort=sort,
            visible=visible,
            status=1,
        )
        db.add(menu)
        await db.flush()
        existing.append(menu)
        created_menus.append(menu)

    if created_menus:
        logger.info(f"Created {len(created_menus)} aegis_agent menus")

    # ── 3. 绑定到 admin 角色 ──────────────────────────
    admin_result = await db.execute(select(Role).where(Role.code == "admin"))
    admin_role = admin_result.scalars().first()
    if admin_role and created_menus:
        bound_ids = {m.id for m in admin_role.menus}
        new_bindings = [
            {"role_id": admin_role.id, "menu_id": menu.id}
            for menu in created_menus
            if menu.id not in bound_ids
        ]
        if new_bindings:
            from sqlalchemy import insert
            await db.execute(insert(role_menu), new_bindings)
            await db.flush()
            logger.info(f"Bound {len(new_bindings)} aegis_agent menus to admin role")
