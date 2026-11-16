# СИС 3: сервис заказов на AWS — пошаговая инструкция

Основа: Week11_Infrastructure_as_Code, слайд 32. Это готовый учебный вариант, покрывающий перечисленные на этом слайде требования. Если преподаватель выдал отдельный rubric или требует продолжить именно ваш прошлый проект, учитывайте и его: такого файла здесь нет.

Проект проверен локально: CloudFormation lint, проверки правил, тесты обработчика. В вашем AWS-аккаунте он ещё не развёрнут. Скриншоты и результаты защиты нужно получить после выполнения инструкции.

## 1. Что получится

```text
POST /orders → ALB → ECS Fargate API → SNS topic → SQS → consumer → DynamoDB
                                                   │
                                                   └─ после ошибок → DLQ
GET /orders/{eventId} → ALB → ECS API → DynamoDB
Логи API и consumer → CloudWatch Logs, хранение 7 дней
Образ контейнера → ECR, immutable tag = git commit SHA
Все облачные ресурсы → CloudFormation
```

API и обработчик очереди работают в одном учебном контейнере. В dev запускается одна task, в staging/prod — две. DynamoDB хранит и результат обработки, и ключ дедупликации одной атомарной записью.

Это лабораторный HTTP API без авторизации. Используй вымышленные заказы. Название `prod` меняет число tasks, но не делает этот учебный пример готовым для production.

ALB, Fargate, IPv4 и другие ресурсы могут стоить денег. Бесплатность аккаунта или наличие кредитов не гарантирует отсутствие списаний. NAT Gateway в проекте нет. После тренировки удали копию, после защиты — основную систему.

## 2. Скачай и распакуй архив

1. Скачай `sis3-orders.zip` из сообщения.
2. Открой Downloads / Загрузки.
3. На Mac дважды нажми на ZIP. Появится папка `sis3-orders`.
4. Открой её. Внутри должны быть `app.py`, `worker.py`, `Dockerfile`, `deploy.sh`, папки `infra` и `tests`.
5. На Mac нажми **Cmd + Shift + .**, чтобы увидеть `.gitignore` и `.dockerignore`. На Windows включи показ скрытых файлов в Проводнике.

Не нужно перепечатывать код, создавать VPC или очереди вручную.

## 3. Создай GitHub-репозиторий

1. Открой https://github.com и войди в свой аккаунт.
2. Нажми **+** в верхней части страницы → **New repository**. Можно сразу открыть https://github.com/new.
3. В **Repository name** введи `sis3-orders`.
4. Выбери **Public**, чтобы затем клонировать без настройки GitHub-авторизации в CloudShell. В исходниках нет паролей AWS.
5. Включи **Add a README file**.
6. Нажми **Create repository**.
7. На странице репозитория нажми **Add file → Upload files**. Если интерфейс показывает кнопку `+` над списком файлов, ищи **Upload files** там.
8. В Finder открой распакованную папку `sis3-orders`.
9. Выдели её СОДЕРЖИМОЕ, включая папки `infra`, `tests`, скрытые `.gitignore` и `.dockerignore`, и перетащи в область загрузки GitHub. Не перетаскивай саму внешнюю папку `sis3-orders`.
10. Проверь пути в списке загрузки: `app.py`, `infra/app.yaml`, `tests/test_worker.py`. Путь `sis3-orders/app.py` означает лишний уровень папки: отмени и загрузи содержимое.
11. Внизу в сообщении коммита напиши `Add SIS3 infrastructure and orders application`.
12. Нажми **Commit changes**. Если GitHub спрашивает ветку, выбери прямой коммит в `main`.
13. Проверь, что в корне есть `deploy.sh`, а в `infra` — два YAML-файла.
14. Сохрани ссылку вида `https://github.com/ТВОЙ_ЛОГИН/sis3-orders`.

Если репозиторий уже существует, используй другое свободное имя и подставь его в командах клонирования ниже. Для частного репозитория понадобится отдельно настроенная GitHub-авторизация.

## 4. Войди в AWS и выбери регион

1. Открой https://console.aws.amazon.com/.
2. Войди под выданной учебной учётной записью или своей рабочей ролью.
3. Если используешь AWS Academy: сначала открой курс → Learner Lab → **Start Lab**, дождись готовности лаборатории, затем нажми ссылку **AWS**.
4. В правой верхней части AWS Console открой список регионов.
5. Выбери **US East (N. Virginia), us-east-1**, если он разрешён твоей лабораторией.
6. Дальше работай в одном регионе. Если у курса разрешён другой регион, выбери его и замени `us-east-1` в командах на него.

Нужны права на CloudFormation, ECR, ECS, EC2/VPC, ELB, SNS, SQS, DynamoDB, CloudWatch Logs, создание IAM roles и `iam:PassRole`. В ограниченном Learner Lab создание собственных ролей может быть запрещено. При такой ошибке нужен разрешённый преподавателем вариант с существующими ролями; этот пакет создаёт две роли сам. Не выдавай себе права через root для обхода ограничений курса.

## 5. Открой CloudShell

1. В верхнюю строку поиска AWS введи `CloudShell`.
2. Нажми результат **CloudShell**. Также можно использовать значок терминала `>_` в панели AWS.
3. Если появится приветствие, нажми **Close** или **Continue**.
4. Дождись приглашения командной строки.
5. Используй обычное окружение CloudShell. Создавать VPC environment для этой работы не нужно.
6. Все команды далее вставляй в ЭТО окно, а не в Terminal на Mac.
7. Вставка на Mac: Cmd+V. После каждого блока нажимай Enter и дожидайся завершения.

AWS CLI и Docker уже есть в CloudShell. `aws configure` и создание AWS access keys здесь не нужны.

Вставь:

```bash
export AWS_DEFAULT_REGION=us-east-1
export AWS_PAGER=""
aws sts get-caller-identity
docker --version
docker info >/dev/null && echo DOCKER_OK
git --version
```

Ожидаемо: JSON с Account/Arn, версия Docker, строка `DOCKER_OK`, версия Git. Если вывод содержит AccessDenied, сначала разбери проблему доступа. Не запускай следующие шаги вслепую.

## 6. Скачай проект из GitHub

В следующем блоке замени только `YOUR_GITHUB_LOGIN` на свой логин GitHub. Если изменил название репозитория, замени и `sis3-orders`.

```bash
git clone https://github.com/YOUR_GITHUB_LOGIN/sis3-orders.git
cd sis3-orders
ls -la
git status --short
```

Ожидаемо: видны файлы проекта; последняя команда не выводит ничего. Это чистая копия репозитория.

Если Git просит Username для Public-репозитория, проверь логин, имя и доступность репозитория в браузере: часто это опечатка или репозиторий всё-таки Private.

## 7. Установи средства проверки и запусти проверки

Проверки выполняются до создания платных ресурсов. Для них нужен Python 3.10 или новее. В CloudShell можно установить Python 3.11:

```bash
sudo dnf install -y python3.11 python3.11-pip
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
bash check.sh
```

Папка `.venv` исключена из Git. При перезапуске среды CloudShell системную установку Python может потребоваться повторить.

Ожидаемо:

* Тесты заканчиваются `OK`.
* `cfn-lint` не выводит ошибок.
* Появляется `Lab policy checks passed`.
* В конце: `All local checks passed`.

Проверки правил здесь реализует небольшой `policy_check.py`: шифрование, две роли, DLQ, срок логов, rollback, immutable tags и отсутствие NAT. Это учебная проверка конкретных правил, не полный security audit и не заявление о прохождении Checkov. На слайде 29 как инструменты policy-as-code названы cfn-guard/Checkov; если преподаватель требует именно один из них, нужно дополнительно запустить требуемый инструмент и разобрать его вывод.

## 8. Разверни основную систему одной командой

```bash
bash deploy.sh sis3-main dev
```

Что делает команда:

1. Проверяет, кто ты в AWS, доступность Docker и чистоту Git.
2. Готовит change set для `sis3-main-registry`.
3. Показывает таблицу изменений ECR.
4. Спрашивает `Execute change set for sis3-main-registry? [y/N]`.
5. При первом запуске ожидается `Add Repository`. Если это так, введи `y`, Enter.
6. Дожидается создания реестра.
7. Собирает контейнер, ставит tag текущего git commit и отправляет в ECR.
8. Готовит change set для `sis3-main-app`.
9. Показывает таблицу ресурсов приложения.
10. Спрашивает `Execute change set for sis3-main-app? [y/N]`.
11. При первом запуске ожидаются строки `Add`: VPC, очереди, роли, ALB, ECS и другие ресурсы. Просмотри список, затем введи `y`, Enter.
12. Дожидается готовности и выводит `Deployment complete` с таблицей Outputs.

В существующем стеке проверяй `Remove`, `Replacement=True` и `Conditional`: они могут означать удаление или замену ресурса. Не подтверждай их автоматически.

Создание ECS/ALB может занимать несколько минут и больше. Не закрывай вкладку. Если скрипт ждёт `y`, это видно по вопросу в последней строке. Если он ожидает AWS, можно смотреть состояние во второй вкладке консоли.

Скрипт создаёт два самостоятельных стека. Реестр выделен, потому что образ нужно отправить до создания ECS service. Основной стек получает URI образа параметром. Сетевые и прикладные ресурсы для простоты учебной работы объединены в одном шаблоне. Разделение network/data/app на слайде 15 предложено как рекомендуемый вариант, а не отдельный пункт списка слайда 32.

## 9. Посмотри состояние CloudFormation

1. Открой вторую вкладку AWS Console.
2. В поиске введи `CloudFormation` → открой сервис.
3. Слева нажми **Stacks**.
4. Найди `sis3-main-registry` и `sis3-main-app`.
5. У обоих после успешного первого запуска должен быть **CREATE_COMPLETE**. После обновления допустим **UPDATE_COMPLETE**.
6. Открой `sis3-main-app`.
7. **Resources** показывает все созданные ресурсы. Здесь можно переходить по Physical ID.
8. **Parameters** показывает `Env=dev`, `ImageUri`, `AllowedCidr`.
9. **Template** показывает исходный шаблон.
10. **Outputs** содержит адрес API, имена таблицы, очередей, логов и ролей.
11. **Events** помогает находить причины ошибок.
12. **Change sets** позволяет показать подготовленный/исполненный список изменений.

Сделай скриншот списка стеков с успешным статусом и Outputs приложения.

## 10. Проверь API и обработку заказа

Вернись в CloudShell, находясь в папке проекта:

```bash
source outputs.sh sis3-main
curl -i "$API/health"
```

Ожидаемо: `HTTP/1.1 200 OK` и `{"status":"ok","environment":"dev"}` с возможными пробелами.

Для проверки в браузере скопируй напечатанный `API=http://...` без префикса `API=`, добавь `/health` и открой. Используй `http://`, поскольку учебный ALB здесь без HTTPS-сертификата.

Отправь заказ:

```bash
curl -i -X POST "$API/orders" \
  -H 'Content-Type: application/json' \
  -d '{"eventId":"order-001","sku":"book","quantity":1}'
```

Ожидаемо: **202 Accepted**, `status=QUEUED`, `eventId=order-001`. Это подтверждение приёма в SNS, а не завершения обработки.

Через несколько секунд проверь:

```bash
curl -i "$API/orders/order-001"
```

Ожидаемо: **200**, `status=PROCESSED` и исходный заказ. Если сначала **404 / NOT_PROCESSED_YET**, повтори через несколько секунд. Если запись не появляется, смотри CloudWatch.

Сделай скриншоты ответа 202 и результата PROCESSED.

## 11. Докажи идемпотентность

Снова отправь тот же ключ:

```bash
curl -i -X POST "$API/orders" \
  -H 'Content-Type: application/json' \
  -d '{"eventId":"order-001","sku":"book","quantity":1}'
```

У API снова будет 202: публикации разные, но бизнес-событие имеет тот же `eventId`. Обработчик не создаёт второй заказ и не перезаписывает первый.

Посмотри логи:

```bash
aws logs tail "$LOGS" --since 15m --format short
```

Нужные строки:

```json
{"action":"processed","eventId":"order-001"}
{"action":"duplicate_skipped","eventId":"order-001"}
```

SQS допускает повторную доставку, поэтому `duplicate_skipped` может появиться и раньше ручного повтора.

Проверь таблицу:

```bash
aws dynamodb get-item --table-name "$TABLE" \
  --key '{"eventId":{"S":"order-001"}}' --consistent-read
```

Где нажимать в AWS:

1. Поиск → **DynamoDB**.
2. Слева **Tables** → выбери таблицу, имя которой вывел `$TABLE`.
3. Нажми **Explore table items**. Если есть отдельный пункт **Explore items** слева, открой его и выбери таблицу.
4. При необходимости нажми **Run**, затем **Refresh**.
5. Найди `eventId=order-001`. Для этого ключа должна быть одна запись.

Само наличие одной строки в таблице с таким partition key ещё не доказывает отсутствие повторной перезаписи. Поэтому на защите покажи также `duplicate_skipped` и код `ConditionExpression="attribute_not_exists(eventId)"` в `worker.py`.

Полезная дополнительная демонстрация: отправь тот же `eventId` с `sku="changed"`; API GET должен по-прежнему вернуть первый `sku="book"`. Это поведение «первое событие с ключом побеждает». Для нового заказа всегда используй новый `eventId`.

## 12. Докажи работу DLQ

Отправь специальный учебный заказ, который обработчик намеренно не может обработать:

```bash
curl -i -X POST "$API/orders" \
  -H 'Content-Type: application/json' \
  -d '{"eventId":"bad-001","sku":"broken-demo","quantity":1,"forceFail":true}'
```

Ожидаемо: 202 на публикации. Затем в логах появляются `processing_failed`. Обработчик не удаляет такое сообщение из SQS.

В шаблоне: `VisibilityTimeout=30`, `maxReceiveCount=3`. Нужно дождаться нескольких получений и переноса сообщения. Проверяй примерно через 2–3 минуты; это ориентир, точное время AWS не гарантирует.

```bash
aws sqs get-queue-attributes --queue-url "$DLQ" \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
```

Ожидаемо: `ApproximateNumberOfMessages` не меньше 1 после переноса. Метрики приблизительные и обновляются с задержкой.

Посмотри тело сообщения:

```bash
aws sqs receive-message --queue-url "$DLQ" \
  --max-number-of-messages 1 --wait-time-seconds 10 --visibility-timeout 5
```

В `Body` должен быть `eventId=bad-001`. Эта команда не удаляет сообщение, но временно скрывает его на 5 секунд. Не запускай receive-message многократно в основной рабочей очереди во время демонстрации: её уже читает приложение.

Где нажимать:

1. Поиск AWS → **SQS** → **Queues**.
2. Чтобы найти точную очередь, открой CloudFormation → `sis3-main-app` → Resources → `OrdersQueue` или `DeadLetterQueue` → Physical ID.
3. В `OrdersQueue` найди секцию/вкладку **Dead-letter queue** и покажи привязанную DLQ и Maximum receives = 3.
4. Открой `DeadLetterQueue`.
5. Нажми **Send and receive messages**.
6. В секции получения нажми **Poll for messages**.
7. Нажми на найденный Message ID → открой **Body**.
8. Покажи `bad-001` и сделай скриншот. Не нажимай Delete, если хочешь оставить сообщение для защиты.

## 13. Проверь SNS, ECR, ECS, ALB и логи

### SNS

1. Поиск → **SNS / Simple Notification Service**.
2. Слева **Topics** → открой topic из CloudFormation Resources → `Topic`.
3. В **Subscriptions** покажи подписку: Protocol = **SQS**, Status = **Confirmed**.
4. Открой подписку и покажи **Raw message delivery = Enabled**.

SNS передаёт `OrderCreated` в SQS. Raw delivery означает, что consumer получает исходный JSON без внешней SNS-обёртки.

### ECR

1. Поиск → **ECR / Elastic Container Registry**.
2. Открой **Private registry → Repositories** или **Private repositories**.
3. Выбери реестр из `sis3-main-registry` → Resources → `Repository`.
4. В **Images** покажи образ. Его tag — commit SHA, не `latest`.
5. В настройках репозитория покажи **Tag immutability / Image tag mutability = Immutable**.
6. В **Lifecycle policy** покажи правило: удалять untagged-образы старше одного дня.

Правило намеренно касается untagged-образов: автоматическое удаление старых tagged-образов могло бы удалить образ, на который ссылается ещё работающий стек.

### ECS

1. Поиск → **ECS / Elastic Container Service**.
2. Слева **Clusters** → выбери кластер из Outputs `ClusterName`.
3. Открой **Services** → сервис из `ServiceName`.
4. Покажи Desired = 1 и Running = 1 в окружении dev.
5. Открой **Tasks** → работающую task. Покажи Launch type / Capacity = **Fargate**.
6. Открой ссылку на **Task definition** и её текущую revision.
7. В деталях task definition покажи **Task role** и **Task execution role**. Это две разные IAM-роли.
8. Execution role нужна ECS для загрузки образа из ECR и отправки логов. Task role нужна приложению для SNS, SQS и DynamoDB.

### ALB

1. Поиск → **EC2**.
2. В левом меню прокрути до **Load Balancing → Load Balancers**.
3. Открой ALB, Physical ID которого указан у `LoadBalancer` в CloudFormation.
4. Покажи тип **Application**, Scheme = **internet-facing**, DNS name.
5. В левом меню **Target Groups** → группа из ресурса `TargetGroup`.
6. Открой вкладку **Targets** → цель должна иметь статус **Healthy**.
7. В **Health checks** покажи путь `/health`.

Task запускается с public IP, чтобы обращаться к AWS API без NAT. Её порт 8080 разрешён только из security group ALB. Две публичные подсети нужны ALB в двух зонах доступности; отдельная VPC создаётся для каждой копии.

### CloudWatch

1. Поиск → **CloudWatch**.
2. Слева **Logs → Log groups**.
3. Найди группу из Outputs `LogGroup`.
4. Покажи **Retention = 1 week / 7 days**.
5. Открой log group → **Log streams** → свежий stream.
6. Найди `processed`, `duplicate_skipped`, `processing_failed`.
7. Сделай скриншоты.

Названия некоторых вкладок могут немного отличаться. Всегда можно открыть точный ресурс через CloudFormation → Resources → Physical ID.

## 14. Повтори deploy без изменений

Вернись в CloudShell в папку проекта:

```bash
bash deploy.sh sis3-main dev
```

Ожидаемо: `No changes to deploy` для шаблонов, reuse существующего immutable image и те же Outputs. Новые VPC, очереди или таблицы не должны появляться. Это полезная демонстрация декларативности.

## 15. Главный тест защиты: новая копия из чистого checkout

Не удаляй первую систему. Создай отдельный чистый checkout из GitHub:

```bash
cd ..
git clone https://github.com/YOUR_GITHUB_LOGIN/sis3-orders.git sis3-clean
cd sis3-clean
git status --short
bash deploy.sh sis3-copy dev
```

Снова замени `YOUR_GITHUB_LOGIN`. При первом выполнении новая папка `sis3-clean` должна отсутствовать. Если ты уже проходил шаг, используй свободное имя папки.

На подтверждениях сначала просмотри Add-ресурсы для `sis3-copy-registry` и `sis3-copy-app`, затем введи `y`.

После успеха:

```bash
source outputs.sh sis3-copy
curl -i "$API/health"
curl -i -X POST "$API/orders" \
  -H 'Content-Type: application/json' \
  -d '{"eventId":"copy-001","sku":"book","quantity":1}'
```

Через несколько секунд:

```bash
curl -i "$API/orders/copy-001"
```

Покажи в CloudFormation четыре стека: main-registry, main-app, copy-registry, copy-app. У каждой копии свой ALB URL, очереди, таблица и реестр. Консоль для ручного создания ресурсов не понадобилась. Подтверждение change set — часть review, а не ручная настройка инфраструктуры.

Новая копия имеет пустую таблицу. Заказы первой системы не копируются: IaC воспроизводит инфраструктуру, перенос данных — отдельная задача.

## 16. Какие скриншоты и файлы подготовить

Минимальный набор доказательств для перечисленных требований:

| Что показать | Где |
|---|---|
| Код, Dockerfile, два шаблона, README | GitHub |
| Успешные проверки | CloudShell, `bash check.sh` |
| Подготовленный/исполненный change set | CloudFormation |
| Стек развёрнут и Outputs | CloudFormation |
| SNS-подписка на SQS | SNS |
| DLQ и Maximum receives = 3 | SQS |
| Сообщение bad-001 в DLQ | SQS |
| Commit tag, Immutable, lifecycle rule | ECR |
| Running task на Fargate | ECS |
| Две отдельные роли | Task definition |
| ALB target Healthy и /health 200 | EC2/браузер |
| Retention 7 days и строки processed/duplicate_skipped | CloudWatch |
| Одна запись заказа | DynamoDB |
| Вторая независимая копия из GitHub | CloudShell + CloudFormation |

На слайде 33 сказано принести репозиторий, шаблон и развёрнутый стек. Отдельный PDF-отчёт в предоставленной презентации не указан. Если в LMS есть отдельное поле отчёта или требования к оформлению, следуй им.

## 17. Что говорить на защите

> Я реализовал сервис заказов. POST /orders публикует доменное событие OrderCreated в SNS. Подписка доставляет его в SQS. Обработчик в ECS Fargate сохраняет результат в DynamoDB.
>
> Ключ идемпотентности — eventId, он же partition key таблицы. Запись заказа использует условие attribute_not_exists(eventId). Это одна атомарная операция: при повторной доставке обработчик пишет duplicate_skipped и удаляет уже обработанное сообщение из очереди. Если запись в DynamoDB не удалась, сообщение не удаляется и будет повторено.
>
> Для ошибок настроена DLQ с maxReceiveCount=3. В учебной демонстрации forceFail=true вызывает ошибку, после повторов сообщение попадает в DLQ.
>
> Образ хранится в ECR с immutable tag по commit SHA и lifecycle policy. Приложение работает в Fargate за ALB, логи идут в CloudWatch на 7 дней. Execution role и task role разделены.
>
> Все облачные ресурсы описаны CloudFormation, окружение задаётся параметром Env. В шаблонах нет секретов. Одна команда bash deploy.sh sis3-copy dev из чистого checkout создаёт независимую копию системы.

Что понимать, а не просто заучить:

* SQS Standard может повторно доставлять сообщение. Этот пример делает идемпотентной запись заказа, не обещает exactly-once доставку транспорта.
* Если контейнер упадёт после DynamoDB PutItem, но до DeleteMessage, повторная обработка наткнётся на уже существующий eventId и безопасно подтвердит сообщение.
* Если к заказу добавить внешний побочный эффект вроде оплаты или email, одной такой записи уже недостаточно для его идемпотентности. В данном проекте бизнес-эффект ограничен записью заказа.
* Visibility timeout скрывает сообщение от других consumer на время обработки. maxReceiveCount ограничивает количество получений перед переносом в DLQ.
* SNS распределяет события подписчикам, SQS хранит сообщения до обработки.
* API отвечает 202 до обработки, потому что цепочка асинхронная.
* No changes to deploy означает отсутствие разницы шаблонов. Это само по себе не проверка drift.

## 18. Если что-то не работает

### AccessDenied / iam:CreateRole / iam:PassRole

Это ограничение прав аккаунта. CloudShell использует ту же роль, что и консоль. Сохрани точный текст ошибки и уточни у преподавателя, разрешено ли создавать две роли или нужно подставить заранее выданные. Замена на одну LabRole может нарушить требование «две отдельные роли», поэтому её нельзя молча считать эквивалентной.

### CloudFormation failed / ROLLBACK_COMPLETE

1. CloudFormation → проблемный стек → **Events**.
2. События обычно идут от новых к старым. Найди самое раннее содержательное `CREATE_FAILED`, а не последующие `Resource creation cancelled`.
3. Прочитай **Status reason**.
4. Исправляй код/шаблон и делай git commit, не чиня управляемые ресурсы вручную в консоли.
5. При `ROLLBACK_COMPLETE` после первого неудачного создания стек нельзя обновить. После выяснения причины удали именно этот неудачный стек и дождись удаления:

```bash
aws cloudformation delete-stack --stack-name sis3-main-app
aws cloudformation wait stack-delete-complete --stack-name sis3-main-app
```

6. Если неудачный стек был `sis3-main-registry`, в этих двух командах используй его имя.
7. После исправления и коммита повтори `bash deploy.sh sis3-main dev`.
8. Для `UPDATE_ROLLBACK_COMPLETE` исправь причину и повтори deploy. Для `UPDATE_ROLLBACK_FAILED` сначала нужно восстановить rollback, а не удалять работающую систему вслепую.

Для просмотра ошибок в CloudShell:

```bash
aws cloudformation describe-stack-events --stack-name sis3-main-app \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`].[Timestamp,LogicalResourceId,ResourceStatusReason]' \
  --output table
```

### Скрипт перестал ждать, а стек ещё создаётся

Проверь CloudFormation Events и статус. Таймаут ожидания команды не всегда означает провал AWS. Не запускай второй deploy, пока текущая операция не закончится. После CREATE_COMPLETE/UPDATE_COMPLETE можно выполнить `source outputs.sh sis3-main` и проверить API.

### ECS task не запускается / ALB 503

1. ECS → Cluster → Service → **Events**.
2. Открой **Tasks**, включи показ **Stopped**, выбери последнюю остановленную task.
3. Прочитай **Stopped reason** и причину остановки контейнера.
4. `CannotPullContainerError`: проверь наличие commit tag в ECR и сетевой доступ.
5. `AccessDenied`: проверь ExecutionRole или TaskRole в зависимости от неудачной операции.
6. Открой CloudWatch log group из Outputs.
7. EC2 → Target Groups → Targets: проверь Healthy и health check `/health`.

### API 404 для заказа

Сначала дождись обработки, затем смотри `poll_error`/`processing_failed` в логах. Проверь, что `$API` относится к нужной копии: `source outputs.sh sis3-main` или `source outputs.sh sis3-copy`. Заказ bad-001 намеренно не сохраняется.

### DLQ пустая

Проверь: отправлен именно `forceFail:true`, API вернул 202, worker работает и пишет processing_failed. Дай пройти нескольким циклам VisibilityTimeout. Если ты только что получал сообщение из DLQ, оно временно невидимо до окончания visibility timeout.

### Git working tree is not clean

```bash
git status --short
```

Если менял исходники, проверь изменения и сделай commit перед deploy. Если правки нужны на защите из чистого GitHub checkout, отправь их в GitHub. `.venv` и кэш Python не должны попадать в коммит.

### Docker cannot connect / no space left

Если daemon недоступен, CloudShell → Actions → Restart AWS CloudShell, затем вернись в папку проекта и повтори проверки. Если кончилось место, посмотри `docker system df` и удаляй только свои ненужные локальные образы. Не удаляй ECR-образы работающего стека.

### Нужно открыть CloudShell заново

```bash
cd ~/sis3-orders
export AWS_DEFAULT_REGION=us-east-1
export AWS_PAGER=""
source outputs.sh sis3-main
```

Если нужны локальные проверки, снова активируй `.venv`. Если системный Python 3.11 исчез после обновления среды, повтори его установку из шага 7.

## 19. Удали ресурсы после тренировки и защиты

Сначала удали тренировочную копию, сохранив основную до защиты:

```bash
bash cleanup.sh sis3-copy
```

Скрипт спросит подтверждение. Введи **sis3-copy**, Enter. Он удалит app, дождётся завершения, затем удалит registry вместе с образами.

После защиты основной системы:

```bash
bash cleanup.sh sis3-main
```

Введи **sis3-main**, Enter.

В этой лабораторной конфигурации данные DynamoDB и CloudWatch Logs удаляются вместе с app-стеком. Для реальной системы потребовались бы отдельные политики сохранения и резервирования данных.

Проверь в консоли CloudFormation, что активных стеков main/copy больше нет, и что связанные ALB и ECS services удалены. Удалённые стеки могут оставаться в истории как DELETE_COMPLETE. Если статус DELETE_FAILED, открой Events и устрани указанную причину. Остановка AWS Academy Lab или закрытие CloudShell не заменяет удаление ресурсов.

## 20. Где какой файл

| Файл | Назначение |
|---|---|
| app.py | HTTP API: /health, POST /orders, GET /orders/{eventId} |
| worker.py | Чтение SQS, атомарная запись, обработка дубликатов |
| Dockerfile | Сборка контейнера, непривилегированный пользователь |
| infra/registry.yaml | ECR, immutable tags, lifecycle policy |
| infra/app.yaml | VPC, ALB, ECS, роли, SNS, SQS/DLQ, DynamoDB, логи |
| deploy.sh | Подготовка/review change sets, build/push, deploy |
| outputs.sh | Получение адресов и имён ресурсов |
| cleanup.sh | Удаление обеих частей одной копии |
| check.sh | Тесты, cfn-lint, проверки правил |
| policy_check.py | Конкретные учебные ограничения конфигурации |
| tests/test_worker.py | Дубликаты, атомарная запись, ошибки хранилища и сообщения |

## Источники

* Предоставленная презентация Week11_Infrastructure_as_Code: слайды 15, 29, 32–33.
* AWS CloudShell / Docker: https://docs.aws.amazon.com/cloudshell/latest/userguide/working-with-aws-cloudshell.html
* Change set review: https://docs.aws.amazon.com/cli/latest/reference/cloudformation/deploy.html
* ECS execution role: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html
* ECS networking: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html
* SNS raw delivery: https://docs.aws.amazon.com/sns/latest/dg/sns-large-payload-raw-message-delivery.html
* ECR CloudFormation: https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ecr-repository.html
