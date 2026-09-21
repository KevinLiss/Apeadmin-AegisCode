"""AegisCode 工作区菜单注册。"""

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Menu, Role
from src.models.rbac import role_menu


async def seed_aegis_workspace_data(db: AsyncSession) -> None:
    """Seed 菜单 + 权限 + 绑定 admin 角色。幂等。"""

    # 找到或创建 AegisCode 顶级目录（aegis_agent 可能已创建）
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

    menu_specs = [
        ("工作区管理", "AegisCode", "C", "workspace", "aegis_workspace/projects/index", "aegis_workspace:projects:list", "Folder", 3),
        ("创建项目", "工作区管理", "F", None, None, "aegis_workspace:projects:create", None, 1),
        ("编辑项目", "工作区管理", "F", None, None, "aegis_workspace:projects:edit", None, 2),
        ("删除项目", "工作区管理", "F", None, None, "aegis_workspace:projects:delete", None, 3),
        ("执行命令", "工作区管理", "F", None, None, "aegis_workspace:execute", None, 4),
        ("Git 快照", "工作区管理", "F", None, None, "aegis_workspace:snapshot", None, 5),
        ("成员管理", "工作区管理", "F", None, None, "aegis_workspace:members:manage", None, 6),
    ]

    existing = list((await db.execute(select(Menu))).scalars().all())
    created_menus: list[Menu] = []

    for name, parent_name, mtype, path, component, permission, icon, sort in menu_specs:
        parent_menu = next((m for m in existing + created_menus if m.name == parent_name), None)
        if not parent_menu:
            continue
        dup = any(m.name == name and m.parent_id == parent_menu.id for m in existing)
        if dup:
            continue
        menu = Menu(
            name=name, parent_id=parent_menu.id, type=mtype,
            path=path, component=component, permission=permission,
            icon=icon, sort=sort, visible=1, status=1,
        )
        db.add(menu)
        await db.flush()
        existing.append(menu)
        created_menus.append(menu)

    if created_menus:
        logger.info(f"Created {len(created_menus)} aegis_workspace menus")

    admin_result = await db.execute(select(Role).where(Role.code == "admin"))
    admin_role = admin_result.scalars().first()
    if admin_role and created_menus:
        bound_ids = {m.id for m in admin_role.menus}
        new_bindings = [
            {"role_id": admin_role.id, "menu_id": m.id}
            for m in created_menus if m.id not in bound_ids
        ]
        if new_bindings:
            from sqlalchemy import insert
            await db.execute(insert(role_menu), new_bindings)
            await db.flush()
            logger.info(f"Bound {len(new_bindings)} aegis_workspace menus to admin role")
