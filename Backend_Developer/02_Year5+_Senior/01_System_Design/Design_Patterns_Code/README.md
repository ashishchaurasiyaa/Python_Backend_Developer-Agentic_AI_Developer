# Design Patterns — Runnable Django Projects

This directory contains **16 runnable implementations** of classical and enterprise design patterns, each built as a self-contained Django mini-project that mirrors real scenarios from the Youngman India B2B scaffolding ERP.

Patterns 01–14 are **full Django projects** (project config directory + domain app + `manage.py`). Patterns 15–20 are **standalone Python scripts** demonstrating the core pattern mechanics without the full web stack.

---

## Pattern Index

| # | Pattern Name | Directory | Django Project Dir | App Dir | LLD Theory |
|---|---|---|---|---|---|
| 1 | Singleton | [`01_singleton/`](01_singleton/) | `singleton_project/` | `sap_connector/` | [`01_Singleton_Pattern.md`](../LLD_Theory/01_Singleton_Pattern.md) |
| 2 | Factory Method | [`02_factory/`](02_factory/) | `factory_project/` | `challans/` | [`02_Factory_Pattern.md`](../LLD_Theory/02_Factory_Pattern.md) |
| 3 | Abstract Factory | [`03_abstract_factory/`](03_abstract_factory/) | `abstract_factory_project/` | `sap_documents/` | [`03_Abstract_Factory_Pattern.md`](../LLD_Theory/03_Abstract_Factory_Pattern.md) |
| 4 | Observer | [`04_observer/`](04_observer/) | `observer_project/` | `order_events/` | [`08_Observer_Pattern.md`](../LLD_Theory/08_Observer_Pattern.md) |
| 5 | Builder | [`06_builder/`](06_builder/) | `builder_project/` | `sap_builder/` | [`04_Builder_Pattern.md`](../LLD_Theory/04_Builder_Pattern.md) |
| 6 | Template Method | [`09_template_method/`](09_template_method/) | `template_method_project/` | `reports/` | [`09_Template_Method_Pattern.md`](../LLD_Theory/09_Template_Method_Pattern.md) |
| 7 | Command | [`11_command/`](11_command/) | `command_project/` | `credit_pipeline/` | [`Command_Composite_Proxy_Flyweight_Patterns.md`](../LLD_Theory/Command_Composite_Proxy_Flyweight_Patterns.md) |
| 8 | Repository | [`12_repository/`](12_repository/) | `repository_project/` | `customers/` | [`11_Dependency_Injection_Repository_StateMachine.md`](../LLD_Theory/11_Dependency_Injection_Repository_StateMachine.md) |
| 9 | Service Layer | [`13_service_layer/`](13_service_layer/) | `service_layer_project/` | `challan_management/` | [`11_Dependency_Injection_Repository_StateMachine.md`](../LLD_Theory/11_Dependency_Injection_Repository_StateMachine.md) |
| 10 | Dependency Injection | [`14_dependency_injection/`](14_dependency_injection/) | `di_project/` | `payments/` | [`11_Dependency_Injection_Repository_StateMachine.md`](../LLD_Theory/11_Dependency_Injection_Repository_StateMachine.md) |
| 11 | Prototype | [`15_prototype/`](15_prototype/) | — (script) | `prototype.py` | [`12_Prototype_Pattern.md`](../LLD_Theory/12_Prototype_Pattern.md) |
| 12 | Facade | [`16_facade/`](16_facade/) | — (script) | `facade.py` | [`13_Facade_Pattern.md`](../LLD_Theory/13_Facade_Pattern.md) |
| 13 | Iterator | [`17_iterator/`](17_iterator/) | — (script) | `iterator.py` | [`14_Iterator_Pattern.md`](../LLD_Theory/14_Iterator_Pattern.md) |
| 14 | Mediator | [`18_mediator/`](18_mediator/) | — (script) | `mediator.py` | [`15_Mediator_Pattern.md`](../LLD_Theory/15_Mediator_Pattern.md) |
| 15 | Visitor | [`19_visitor/`](19_visitor/) | — (script) | `visitor.py` | [`16_Visitor_Pattern.md`](../LLD_Theory/16_Visitor_Pattern.md) |
| 16 | Chain of Responsibility | [`20_chain_of_responsibility/`](20_chain_of_responsibility/) | — (script) | `chain.py` | [`17_Chain_of_Responsibility_Pattern.md`](../LLD_Theory/17_Chain_of_Responsibility_Pattern.md) |

---

## Running a Full Django Project

Each directory numbered 01–14 is a standalone Django project. The steps below apply to all of them; replace the path and port as needed.

```bash
# 1. Navigate to the pattern directory
cd Design_Patterns_Code/01_singleton

# 2. Install dependencies (shared requirements at the Design_Patterns_Code level)
pip install django djangorestframework

# 3. Apply migrations
python manage.py migrate

# 4. Start the development server (use a unique port per project to run multiple simultaneously)
python manage.py runserver 8001

# 5. Run the test suite
python manage.py test <app_name> -v2
```

Suggested port assignments so several projects can run side by side:

| Directory | Suggested Port |
|---|---|
| `01_singleton` | 8001 |
| `02_factory` | 8002 |
| `03_abstract_factory` | 8003 |
| `04_observer` | 8004 |
| `06_builder` | 8006 |
| `09_template_method` | 8009 |
| `11_command` | 8011 |
| `12_repository` | 8012 |
| `13_service_layer` | 8013 |
| `14_dependency_injection` | 8014 |

---

## Running a Standalone Script

Patterns 15–20 are pure-Python demonstrations with no database or HTTP layer required.

```bash
cd Design_Patterns_Code/15_prototype
python prototype.py
```

---

## Directory Structure — Full Django Project Layout

```
<pattern_dir>/
├── manage.py                    # Django management entry point
├── <pattern>_project/           # Django project package (settings, urls, wsgi, asgi)
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── <domain_app>/                # Application package implementing the pattern
    ├── models.py
    ├── views.py
    ├── urls.py
    ├── serializers.py
    ├── tests.py
    ├── admin.py
    ├── apps.py
    └── migrations/
```

---

## Related Theory

All theory notes live in [`../LLD_Theory/`](../LLD_Theory/). Additional patterns documented there but not yet implemented as Django projects include:

- [`05_Decorator_Pattern.md`](../LLD_Theory/05_Decorator_Pattern.md)
- [`06_Adapter_Pattern.md`](../LLD_Theory/06_Adapter_Pattern.md)
- [`07_Strategy_Pattern.md`](../LLD_Theory/07_Strategy_Pattern.md)
- [`18_State_Pattern.md`](../LLD_Theory/18_State_Pattern.md)
- [`19_Memento_Pattern.md`](../LLD_Theory/19_Memento_Pattern.md)
- [`20_Bridge_Pattern.md`](../LLD_Theory/20_Bridge_Pattern.md)
- [`21_Interpreter_Pattern.md`](../LLD_Theory/21_Interpreter_Pattern.md)
- [`SOLID_Principles.md`](../LLD_Theory/SOLID_Principles.md)
- [`OOP_Fundamentals.md`](../LLD_Theory/OOP_Fundamentals.md)
- [`Event_Sourcing_CQRS.md`](../LLD_Theory/Event_Sourcing_CQRS.md)
- [`Concurrency_Thread_Safety.md`](../LLD_Theory/Concurrency_Thread_Safety.md)
