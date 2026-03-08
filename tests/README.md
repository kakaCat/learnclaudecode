# 测试文档

## 目录结构

```
tests/
├── unit/                  # 单元测试
│   └── backend/           # 后端单元测试
│       ├── test_exceptions.py    # 异常处理测试
│       ├── test_monitoring.py    # 性能监控测试
│       └── test_new_modules.py   # 新模块验证测试
├── integration/           # 集成测试（待添加）
└── e2e/                   # 端到端测试（待添加）
```

## 运行测试

### 运行所有测试
```bash
pytest tests/
```

### 运行单元测试
```bash
pytest tests/unit/
```

### 运行特定测试文件
```bash
pytest tests/unit/backend/test_exceptions.py -v
pytest tests/unit/backend/test_monitoring.py -v
```

### 查看测试覆盖率
```bash
pytest tests/ --cov=backend --cov-report=html
```

## 测试说明

### test_exceptions.py
测试异常处理模块的所有异常类和工具函数。

### test_monitoring.py
测试性能监控模块的指标收集和报告生成。

### test_new_modules.py
验证新添加模块与现有系统的兼容性。
