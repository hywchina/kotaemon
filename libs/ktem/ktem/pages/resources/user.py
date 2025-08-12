import hashlib

import gradio as gr
import pandas as pd
from ktem.app import BasePage
from ktem.db.models import User, engine
from sqlmodel import Session, select
from theflow.settings import settings as flowsettings

USERNAME_RULE = """**用户名规则:**

- 用户名不区分大小写
- 用户名长度至少3个字符
- 用户名长度最多32个字符
- 用户名只能包含字母、数字和下划线
"""  # translate Username rule --》用户名规则

PASSWORD_RULE = """**密码规则:**

- 密码长度至少8个字符
- 必须包含至少一个大写字母
- 必须包含至少一个小写字母
- 必须包含至少一个数字
- 必须包含至少一个以下特殊字符:
    ^ $ * . [ ] { } ( ) ? - " ! @ # % & / \\ , > < ' : ; | _ ~  + =
"""  # translate Password rule --》密码规则

def validate_username(usn):
    """Validate that whether username is valid

    Args:
        usn (str): Username
    """
    errors = []
    if len(usn) < 3:
        errors.append("用户名长度至少需要3个字符")  # translate Username must be at least 3 characters long --》用户名长度至少需要3个字符

    if len(usn) > 32:
        errors.append("用户名长度不能超过32个字符")  # translate Username must be at most 32 characters long --》用户名长度不能超过32个字符

    if not usn.replace("_", "").isalnum():
        errors.append(
            "用户名只能包含字母、数字和下划线"  # translate Username must contain only... --》用户名只能包含字母、数字和下划线
        )

    return "; ".join(errors)


def validate_password(pwd, pwd_cnf):
    """Validate that whether password is valid

    - Password must be at least 8 characters long
    - Password must contain at least one uppercase letter
    - Password must contain at least one lowercase letter
    - Password must contain at least one digit
    - Password must contain at least one special character from the following:
        ^ $ * . [ ] { } ( ) ? - " ! @ # % & / \\ , > < ' : ; | _ ~  + =

    Args:
        pwd (str): Password
        pwd_cnf (str): Confirm password

    Returns:
        str: Error message if password is not valid
    """
    errors = []
    if pwd != pwd_cnf:
        errors.append("密码不匹配")  # translate Password does not match --》密码不匹配

    if len(pwd) < 8:
        errors.append("密码长度至少需要8个字符")  # translate Password must be at least 8 characters long --》密码长度至少需要8个字符

    if not any(c.isupper() for c in pwd):
        errors.append("密码必须包含至少一个大写字母")  # translate Password must contain at least one uppercase letter --》密码必须包含至少一个大写字母

    if not any(c.islower() for c in pwd):
        errors.append("密码必须包含至少一个小写字母")  # translate Password must contain at least one lowercase letter --》密码必须包含至少一个小写字母

    if not any(c.isdigit() for c in pwd):
        errors.append("密码必须包含至少一个数字")  # translate Password must contain at least one digit --》密码必须包含至少一个数字

    special_chars = "^$*.[]{}()?-\"!@#%&/\\,><':;|_~+="
    if not any(c in special_chars for c in pwd):
        errors.append(
            "密码必须包含至少一个以下特殊字符: "  # translate Password must contain at least one special character... --》密码必须包含至少一个以下特殊字符: 
            f"{special_chars}"
        )

    if errors:
        return "; ".join(errors)

    return ""


def create_user(usn, pwd, user_id=None, is_admin=True) -> bool:
    with Session(engine) as session:
        statement = select(User).where(User.username_lower == usn.lower())
        result = session.exec(statement).all()
        if result:
            print(f'用户"{usn}"已存在')  # translate User "{usn}" already exists --》用户"{usn}"已存在
            return False

        else:
            hashed_password = hashlib.sha256(pwd.encode()).hexdigest()
            user = User(
                id=user_id,
                username=usn,
                username_lower=usn.lower(),
                password=hashed_password,
                admin=is_admin,
            )
            session.add(user)
            session.commit()

            return True


class UserManagement(BasePage):
    def __init__(self, app):
        self._app = app

        self.on_building_ui()
        if hasattr(flowsettings, "KH_FEATURE_USER_MANAGEMENT_ADMIN") and hasattr(
            flowsettings, "KH_FEATURE_USER_MANAGEMENT_PASSWORD"
        ):
            usn = flowsettings.KH_FEATURE_USER_MANAGEMENT_ADMIN
            pwd = flowsettings.KH_FEATURE_USER_MANAGEMENT_PASSWORD

            is_created = create_user(usn, pwd)
            if is_created:
                gr.Info(f'用户"{usn}"创建成功')  # translate User "{usn}" created successfully --》用户"{usn}"创建成功

    def on_building_ui(self):
        with gr.Tab(label="用户列表"):  # translate User list --》用户列表
            self.state_user_list = gr.State(value=None)
            self.user_list = gr.DataFrame(
                headers=["id", "name", "admin"],  # translate
                column_widths=[0, 50, 50],
                interactive=False,
            )

            with gr.Group(visible=False) as self._selected_panel:
                self.selected_user_id = gr.State(value=-1)
                self.usn_edit = gr.Textbox(label="Username")
                with gr.Row():
                    self.pwd_edit = gr.Textbox(label="修改密码", type="password")  # translate Change password --》修改密码
                    self.pwd_cnf_edit = gr.Textbox(
                        label="确认修改密码",  # translate Confirm change password --》确认修改密码
                        type="password",
                    )
                self.admin_edit = gr.Checkbox(label="管理员权限")  # translate Admin --》管理员权限

            with gr.Row(visible=False) as self._selected_panel_btn:
                with gr.Column():
                    self.btn_edit_save = gr.Button("Save")
                with gr.Column():
                    self.btn_delete = gr.Button("Delete")
                    with gr.Row():
                        self.btn_delete_yes = gr.Button(
                            "确认删除", variant="primary", visible=False  # translate Confirm delete --》确认删除
                        )
                        self.btn_delete_no = gr.Button("取消", visible=False)  # translate Cancel --》取消
                with gr.Column():
                    self.btn_close = gr.Button("Close")

        with gr.Tab(label="创建用户"):  # translate Create user --》创建用户
            self.usn_new = gr.Textbox(label="用户名", interactive=True)  # translate Username --》用户名
            self.pwd_new = gr.Textbox(
                label="密码", type="password", interactive=True  # translate Password --》密码
            )
            self.pwd_cnf_new = gr.Textbox(
                label="确认密码", type="password", interactive=True  # translate Confirm password --》确认密码
            )
            with gr.Row():
                gr.Markdown(USERNAME_RULE)  # 保留已翻译的用户名规则
                gr.Markdown(PASSWORD_RULE)  # 保留已翻译的密码规则
            self.btn_new = gr.Button("创建用户")  # translate Create user --》创建用户

    def on_register_events(self):
        self.btn_new.click(
            self.create_user,
            inputs=[self.usn_new, self.pwd_new, self.pwd_cnf_new],
            outputs=[self.usn_new, self.pwd_new, self.pwd_cnf_new],
        ).then(
            self.list_users,
            inputs=self._app.user_id,
            outputs=[self.state_user_list, self.user_list],
        )
        self.user_list.select(
            self.select_user,
            inputs=self.user_list,
            outputs=[self.selected_user_id],
            show_progress="hidden",
        )
        self.selected_user_id.change(
            self.on_selected_user_change,
            inputs=[self.selected_user_id],
            outputs=[
                self._selected_panel,
                self._selected_panel_btn,
                # delete section
                self.btn_delete,
                self.btn_delete_yes,
                self.btn_delete_no,
                # edit section
                self.usn_edit,
                self.pwd_edit,
                self.pwd_cnf_edit,
                self.admin_edit,
            ],
            show_progress="hidden",
        )
        self.btn_delete.click(
            self.on_btn_delete_click,
            inputs=[self.selected_user_id],
            outputs=[self.btn_delete, self.btn_delete_yes, self.btn_delete_no],
            show_progress="hidden",
        )
        self.btn_delete_yes.click(
            self.delete_user,
            inputs=[self._app.user_id, self.selected_user_id],
            outputs=[self.selected_user_id],
            show_progress="hidden",
        ).then(
            self.list_users,
            inputs=self._app.user_id,
            outputs=[self.state_user_list, self.user_list],
        )
        self.btn_delete_no.click(
            lambda: (
                gr.update(visible=True),
                gr.update(visible=False),
                gr.update(visible=False),
            ),
            inputs=[],
            outputs=[self.btn_delete, self.btn_delete_yes, self.btn_delete_no],
            show_progress="hidden",
        )
        self.btn_edit_save.click(
            self.save_user,
            inputs=[
                self.selected_user_id,
                self.usn_edit,
                self.pwd_edit,
                self.pwd_cnf_edit,
                self.admin_edit,
            ],
            outputs=[self.pwd_edit, self.pwd_cnf_edit],
            show_progress="hidden",
        ).then(
            self.list_users,
            inputs=self._app.user_id,
            outputs=[self.state_user_list, self.user_list],
        )
        self.btn_close.click(
            lambda: -1,
            outputs=[self.selected_user_id],
        )

    def on_subscribe_public_events(self):
        self._app.subscribe_event(
            name="onSignIn",
            definition={
                "fn": self.list_users,
                "inputs": [self._app.user_id],
                "outputs": [self.state_user_list, self.user_list],
            },
        )
        self._app.subscribe_event(
            name="onSignOut",
            definition={
                "fn": lambda: ("", "", "", None, None, -1),
                "outputs": [
                    self.usn_new,
                    self.pwd_new,
                    self.pwd_cnf_new,
                    self.state_user_list,
                    self.user_list,
                    self.selected_user_id,
                ],
            },
        )

    def create_user(self, usn, pwd, pwd_cnf):
        errors = validate_username(usn)
        if errors:
            gr.Warning(errors)
            return usn, pwd, pwd_cnf

        errors = validate_password(pwd, pwd_cnf)
        print(errors)
        if errors:
            gr.Warning(errors)
            return usn, pwd, pwd_cnf

        with Session(engine) as session:
            statement = select(User).where(User.username_lower == usn.lower())
            result = session.exec(statement).all()
            if result:
                gr.Warning(f'用户名"{usn}"已存在')  # translate Username "{usn}" already exists --》用户名"{usn}"已存在
                return

            hashed_password = hashlib.sha256(pwd.encode()).hexdigest()
            user = User(
                username=usn, username_lower=usn.lower(), password=hashed_password
            )
            session.add(user)
            session.commit()
            gr.Info(f'用户"{usn}"创建成功')  # translate User "{usn}" created successfully --》用户"{usn}"创建成功

        return "", "", ""

    def list_users(self, user_id):
        if user_id is None:
            return [], pd.DataFrame.from_records(
                [{"id": "-", "username": "-", "admin": "-"}]
            )

        with Session(engine) as session:
            statement = select(User).where(User.id == user_id)
            user = session.exec(statement).one()
            if not user.admin:
                return [], pd.DataFrame.from_records(
                    [{"id": "-", "username": "-", "admin": "-"}]
                )

            statement = select(User)
            results = [
                {"id": user.id, "username": user.username, "admin": user.admin}
                for user in session.exec(statement).all()
            ]
            if results:
                user_list = pd.DataFrame.from_records(results)
            else:
                user_list = pd.DataFrame.from_records(
                    [{"id": "-", "username": "-", "admin": "-"}]
                )

        return results, user_list

    def select_user(self, user_list, ev: gr.SelectData):
        if ev.value == "-" and ev.index[0] == 0:
            gr.Info("当前无用户数据，请刷新用户列表")  # translate No user is loaded. Please refresh the user list --》当前无用户数据，请刷新用户列表
            return -1

        if not ev.selected:
            return -1

        return user_list["id"][ev.index[0]]

    def on_selected_user_change(self, selected_user_id):
        if selected_user_id == -1:
            _selected_panel = gr.update(visible=False)
            _selected_panel_btn = gr.update(visible=False)
            btn_delete = gr.update(visible=True)
            btn_delete_yes = gr.update(visible=False)
            btn_delete_no = gr.update(visible=False)
            usn_edit = gr.update(value="")
            pwd_edit = gr.update(value="")
            pwd_cnf_edit = gr.update(value="")
            admin_edit = gr.update(value=False)
        else:
            _selected_panel = gr.update(visible=True)
            _selected_panel_btn = gr.update(visible=True)
            btn_delete = gr.update(visible=True)
            btn_delete_yes = gr.update(visible=False)
            btn_delete_no = gr.update(visible=False)

            with Session(engine) as session:
                statement = select(User).where(User.id == selected_user_id)
                user = session.exec(statement).one()

            usn_edit = gr.update(value=user.username)
            pwd_edit = gr.update(value="")
            pwd_cnf_edit = gr.update(value="")
            admin_edit = gr.update(value=user.admin)

        return (
            _selected_panel,
            _selected_panel_btn,
            btn_delete,
            btn_delete_yes,
            btn_delete_no,
            usn_edit,
            pwd_edit,
            pwd_cnf_edit,
            admin_edit,
        )

    def on_btn_delete_click(self, selected_user_id):
        if selected_user_id is None:
            gr.Warning("未选择任何用户")  # translate No user is selected --》未选择任何用户
            btn_delete = gr.update(visible=True)
            btn_delete_yes = gr.update(visible=False)
            btn_delete_no = gr.update(visible=False)
            return

        btn_delete = gr.update(visible=False)
        btn_delete_yes = gr.update(visible=True)
        btn_delete_no = gr.update(visible=True)

        return btn_delete, btn_delete_yes, btn_delete_no

    def save_user(self, selected_user_id, usn, pwd, pwd_cnf, admin):
        errors = validate_username(usn)
        if errors:
            gr.Warning(errors)
            return pwd, pwd_cnf

        if pwd:
            errors = validate_password(pwd, pwd_cnf)
            if errors:
                gr.Warning(errors)
                return pwd, pwd_cnf

        with Session(engine) as session:
            statement = select(User).where(User.id == selected_user_id)
            user = session.exec(statement).one()
            user.username = usn
            user.username_lower = usn.lower()
            user.admin = admin
            if pwd:
                user.password = hashlib.sha256(pwd.encode()).hexdigest()
            session.commit()
            gr.Info(f'用户"{usn}"更新成功')  # translate User "{usn}" updated successfully --》用户"{usn}"更新成功

        return "", ""

    def delete_user(self, current_user, selected_user_id):
        if current_user == selected_user_id:
            gr.Warning("无法删除当前登录用户")  # translate You cannot delete yourself --》无法删除当前登录用户
            return selected_user_id

        with Session(engine) as session:
            statement = select(User).where(User.id == selected_user_id)
            user = session.exec(statement).one()
            session.delete(user)
            session.commit()
            gr.Info(f'用户"{user.username}"已删除成功')  # translate User "{user.username}" deleted successfully --》用户"{user.username}"已删除成功
        return -1
