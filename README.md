
# Руководство по эксплуатации Aerogroup Site

## Структура проекта на сервере

```
/www/
├── Aerogroup_site/          — проект
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── nginx/
│   │   └── nginx.conf
│   └── support_ag_ife_com/  — Django
│       ├── manage.py
│       ├── requirements.txt
│       └── .env             — секреты (не в git)
└── backups/                 — бэкапы БД
    └── backup.sh
```

---

## Обновление кода

Когда изменил код в PyCharm и запушил в GitLab:

```bash
cd /www/Aerogroup_site
git pull origin AGsite_v7
docker compose up -d --build web
```

---

## Что пересобирать при разных изменениях

| Что изменил | Команда |
|---|---|
| Код Django, `settings.py`, `requirements.txt` | `docker compose up -d --build web` |
| `nginx.conf` | `docker compose restart nginx` |
| `.env` на сервере | `docker compose up -d --build web` |
| `docker-compose.yml` | `docker compose up -d` |

---

## Создать суперпользователя

```bash
cd /www/Aerogroup_site
docker compose exec web python manage.py createsuperuser
```

---

## Сбросить пароль пользователя

```bash
cd /www/Aerogroup_site
docker compose exec web python manage.py shell -c "
from django.contrib.auth.models import User
u = User.objects.get(username='имя_пользователя')
u.set_password('новый_пароль')
u.save()
print('OK')
"
```

---

## Создать обычного пользователя Django

```bash
cd /www/Aerogroup_site
docker compose exec web python manage.py shell -c "
from django.contrib.auth.models import User
User.objects.create_user('логин', 'email@example.com', 'пароль')
print('OK')
"
```

---

## Посмотреть статус контейнеров

```bash
cd /www/Aerogroup_site
docker compose ps
```

---

## Логи

```bash
# Все контейнеры
docker compose logs -f

# Только Django
docker compose logs -f web

# Только Nginx
docker compose logs -f nginx

# Последние 50 строк Django
docker compose logs --tail=50 web
```

---

## Перезапуск контейнеров

```bash
# Перезапустить все
docker compose restart

# Перезапустить только nginx (например после смены nginx.conf)
docker compose restart nginx

# Полная остановка и запуск
docker compose down
docker compose up -d
```

---

## Бэкап базы данных

Бэкап делается автоматически каждый день в 10:00.
Файлы хранятся 7 дней в `/www/backups/`.

Сделать бэкап вручную:

```bash
/www/backups/backup.sh
ls -lh /www/backups/
```

Восстановить из бэкапа:

```bash
# Разархивировать
gunzip /www/backups/backup_2026-06-10.sql.gz

# Восстановить
docker compose exec -T db psql -U aerogroup_user aerogroup_db < /www/backups/backup_2026-06-10.sql
```

---

## Миграции

Миграции применяются **автоматически** при каждом запуске web контейнера.

Применить вручную:

```bash
docker compose exec web python manage.py migrate
```

Создать новые миграции (после изменения моделей):

```bash
docker compose exec web python manage.py makemigrations
```

---

## SSL сертификат

Сертификат действует до **8 сентября 2026**.
Обновляется автоматически через certbot.

Проверить статус:

```bash
sudo certbot certificates
```

Обновить вручную:

```bash
sudo certbot renew
docker compose restart nginx
```

---

## Добавить переменную в .env

```bash
nano /www/Aerogroup_site/support_ag_ife_com/.env
# Добавить строку, сохранить
docker compose up -d --build web
```

---

## Зайти внутрь контейнера

```bash
# Django контейнер
docker compose exec web bash

# База данных
docker compose exec db psql -U aerogroup_user -d aerogroup_db
```

---

## Если что-то сломалось

1. Смотришь логи: `docker compose logs -f web`
2. Проверяешь статус: `docker compose ps`
3. Перезапускаешь: `docker compose restart`
4. Если не помогло — полный перезапуск:
```bash
docker compose down
docker compose up -d
```
=======
# Supportsite



## Getting started

To make it easy for you to get started with GitLab, here's a list of recommended next steps.

Already a pro? Just edit this README.md and make it your own. Want to make it easy? [Use the template at the bottom](#editing-this-readme)!

## Add your files

* [Create](https://docs.gitlab.com/user/project/repository/web_editor/#create-a-file) or [upload](https://docs.gitlab.com/user/project/repository/web_editor/#upload-a-file) files
* [Add files using the command line](https://docs.gitlab.com/topics/git/add_files/#add-files-to-a-git-repository) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://gitlab.ag-ife.com/support/supportsite.git
git branch -M main
git push -uf origin main
```

## Integrate with your tools

* [Set up project integrations](https://gitlab.ag-ife.com/support/supportsite/-/settings/integrations)

## Collaborate with your team

* [Invite team members and collaborators](https://docs.gitlab.com/user/project/members/)
* [Create a new merge request](https://docs.gitlab.com/user/project/merge_requests/creating_merge_requests/)
* [Automatically close issues from merge requests](https://docs.gitlab.com/user/project/issues/managing_issues/#closing-issues-automatically)
* [Enable merge request approvals](https://docs.gitlab.com/user/project/merge_requests/approvals/)
* [Set auto-merge](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)

## Test and Deploy

Use the built-in continuous integration in GitLab.

* [Get started with GitLab CI/CD](https://docs.gitlab.com/ci/quick_start/)
* [Analyze your code for known vulnerabilities with Static Application Security Testing (SAST)](https://docs.gitlab.com/user/application_security/sast/)
* [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/topics/autodevops/requirements/)
* [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/user/clusters/agent/)
* [Set up protected environments](https://docs.gitlab.com/ci/environments/protected_environments/)

***

# Editing this README

When you're ready to make this README your own, just edit this file and use the handy template below (or feel free to structure it however you want - this is just a starting point!). Thanks to [makeareadme.com](https://www.makeareadme.com/) for this template.

## Suggestions for a good README

Every project is different, so consider which of these sections apply to yours. The sections used in the template are suggestions for most open source projects. Also keep in mind that while a README can be too long and detailed, too long is better than too short. If you think your README is too long, consider utilizing another form of documentation rather than cutting out information.

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

## Badges
On some READMEs, you may see small images that convey metadata, such as whether or not all the tests are passing for the project. You can use Shields to add some to your README. Many services also have instructions for adding a badge.

## Visuals
Depending on what you are making, it can be a good idea to include screenshots or even a video (you'll frequently see GIFs rather than actual videos). Tools like ttygif can help, but check out Asciinema for a more sophisticated method.

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintainers.
>>>>>>> ae7f72121fba881d1da69c843177fef77e755337
