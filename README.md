# ModelMeta — 模型文件元数据生成器

从 GLTF / GLB 文件提取结构化元数据，输出 `.modelmeta.json`；并基于 JSON Schema 自动生成 C++17 结构体与 `nlohmann/json` 序列化代码。

---

## 功能概述

- **解析模型**：读取 `.gltf` / `.glb`，提取包围盒、材质、纹理、骨架等信息。
- **生成元数据**：输出符合 JSON Schema 的 `.modelmeta.json`，支持单文件与批量 glob 模式。
- **纹理解包**：提取内嵌的 Data URI / BufferView 纹理为独立文件，并更新元数据中的相对路径。
- **Schema 驱动**：输出格式由 `schema/modelmeta.schema.json` 定义，修改 Schema 后脚本自动适配。
- **C++ 代码生成**：从同一套 Schema 生成 C++17 Header + `nlohmann/json` `from_json / to_json` 及 `Parse(std::string)` 接口。
- **字段映射**：通过 `symbol_map.py` 维护 JSON 字段名、Python 内部字段、C++ 符号之间的映射，修改映射无需改动核心逻辑。
- **CMake 集成**：提供 `cmake/ModelMetaCodegen.cmake`，可在构建时自动生成 C++ 文件。

---

## 依赖安装

```bash
pip install -r requirements.txt
```

主要依赖：
- `trimesh` — 模型解析
- `pygltflib` — GLTF/GLB 底层读写
- `jsonschema` — Schema 校验
- `clang` (libclang) — C++ 生成后语法验证（可选）

---

## 使用方式

所有参数通过编辑 `model_meta_configs.py` 中的 `GeneratorConfig` 配置，无需 CLI 参数。

```bash
python gltf_meta_generator.py
```

### 配置选项（`model_meta_configs.py`）

| 参数 | 说明 |
|------|------|
| `glob_pattern` | 输入文件匹配模式。`None` 时处理单个文件，例如 `"assets/**/*.glb"` |
| `output_path` | 输出路径。`None`（默认）时在模型文件同级目录就地生成 `.modelmeta.json`；指定目录时输出到该目录 |
| `unpack_textures` | 是否提取内嵌纹理，默认 `True` |
| `texture_output_dir` | 纹理解包输出目录，默认 `"textures"`（相对于 output_path 的上级目录） |
| `schema_path` | JSON Schema 路径，默认 `schema/modelmeta.schema.json` |
| `float_precision` | 浮点数截断位数，`None` 表示不截断，默认 `6` |
| `namespace` | C++ 命名空间，`None` 或 `"dc::meta"` |
| `type_naming` | 类型命名风格：`BigCamel` / `smallCamel` / `snake` / `SCREAMING` |
| `member_naming` | 成员变量命名风格 |
| `enum_naming` | 枚举值命名风格 |
| `function_naming` | 函数签名命名风格 |
| `root_cpp_type` | 根 C++ 类型名，默认 `"ModelMeta"` |
| `parse_function` | 解析函数名，默认 `"Parse"` |

### 默认行为

- `output_path` 未指定时：在模型文件所在目录就地生成 `textures/` 和 `<模型名>.modelmeta.json`
- `glob_pattern` 未指定时：需要传入单个文件路径

---

## 输出格式（`.modelmeta.json`）

字段由 `schema/modelmeta.schema.json` 严格定义，示例如下：

```json
{
  "model_type": "Skeletal",
  "bounding_box": {
    "min": [-1.0, -0.5, -1.0],
    "max": [1.0, 2.0, 1.0]
  },
  "model_part": [
    {
      "model_name": "Body",
      "bounding_box": { "min": [...], "max": [...] },
      "material": {
        "mat_name": "BodyMat",
        "is_pbr": true,
        "textures": {
          "base_color": "textures/model_baseColor.png"
        },
        "alpha_mode": "Opaque",
        "roughness": 0.8,
        "metallic": 0.0
      }
    }
  ],
  "skeleton": [
    {
      "node_name": "Root",
      "model_part": ["Body"]
    }
  ],
  "textures": ["textures/model_baseColor.png"],
  "material": ["BodyMat"]
}
```

| 字段 | 说明 |
|------|------|
| `model_type` | `"Skeletal"`（含骨架）或 `"Static"` |
| `bounding_box` | 整体包围盒，`{ min: float3, max: float3 }` |
| `model_part` | 模型部件数组，含名称、局部包围盒、材质 |
| `material` | PBR 材质信息：名称、纹理槽、透明度模式、粗糙度、金属度 |
| `skeleton` | 骨架节点层级（仅 Skeletal 模型输出） |
| `textures` | 所有材质引用的纹理路径汇总（去重） |
| `material` | 所有材质名称汇总（去重） |

---

## C++ 代码生成

基于同一套 JSON Schema，可同步生成 C++17 结构体与 `nlohmann/json` 序列化代码。

### 生成头文件

```bash
python tools/schema_to_cpp.py schema/modelmeta.schema.json -o include/modelmeta.h
```

- 结构体按依赖关系**拓扑排序**，无需手动调整顺序。
- 生成后自动调用 **libclang** 校验，确保语法 100% 合法。
- 支持 `--namespace dc::meta` 自定义命名空间。

### 生成序列化实现

```bash
python tools/cpp_json_codegen.py schema/modelmeta.schema.json -o src/modelmeta.cpp --header modelmeta.h
```

暴露接口：

```cpp
auto meta = Parse(jsonString);  // 返回根结构体对象
```

### 同步已有头文件

解析已有 `.h`，对比 Schema 差异后重写：

```bash
python tools/schema_to_cpp.py schema/modelmeta.schema.json -o modelmeta.h --sync modelmeta.h
```

### CMake 集成

```cmake
include(cmake/ModelMetaCodegen.cmake)

modelmeta_generate_cpp(
  SCHEMA ${CMAKE_CURRENT_SOURCE_DIR}/schema/modelmeta.schema.json
  HEADER ${CMAKE_CURRENT_BINARY_DIR}/generated/modelmeta.h
  SOURCE ${CMAKE_CURRENT_BINARY_DIR}/generated/modelmeta.cpp
  NAMESPACE dc::meta
)
```

构建时将自动触发 Python 脚本生成 Header 与 `.cpp`。

---

## 项目结构

```
├── gltf_meta_generator.py      # CLI 入口
├── model_meta_configs.py        # 默认配置（命名空间、命名规则、精度等）
├── symbol_map.py               # JSON / C++ 字段与符号映射表
├── schema/
│   └── modelmeta.schema.json   # 元数据 JSON Schema
├── modelmeta/
│   ├── gltf_reader.py          # GLTF/GLB 读取
│   ├── metadata_builder.py     # 构建元数据字典
│   ├── texture_unpacker.py     # 内嵌纹理解包
│   ├── schema_loader.py        # Schema 加载与校验
│   └── output_writer.py        # 输出路径解析与文件写入
├── tools/
│   ├── schema_to_cpp.py        # C++ Header 生成器
│   ├── cpp_json_codegen.py     # nlohmann/json 序列化代码生成器
│   └── cpp_schema.py           # C++ 类型与结构建模
├── cmake/
│   └── ModelMetaCodegen.cmake  # CMake 集成宏
└── .verify/                    # 验证用样本与输出参考
```

---

## 配置与自定义

编辑 `model_meta_configs.py` 可调整：

| 配置项 | 说明 |
|--------|------|
| `namespace` | C++ 命名空间，如 `"dc::meta"` 或 `None` |
| `type_naming` | 结构体命名风格：`BigCamel` / `snake` / `SCREAMING` |
| `member_naming` | 成员变量命名风格 |
| `float_precision` | 浮点数截断位数，`None` 表示不截断 |
| `unpack_textures` | 默认是否解包纹理 |
| `texture_output_dir` | 默认纹理输出目录 |

编辑 `symbol_map.py` 可重命名输出 JSON 字段或生成的 C++ 符号，而无需修改元数据提取逻辑。

---

## 测试

使用 pytest 运行测试：

```bash
pytest
```

验证覆盖：
- 单文件 / glob 批量输出
- `Static` / `Skeletal` 模型类型识别
- 包围盒、材质、纹理、骨架字段正确性
- 纹理解包路径与文件名冲突处理
- Schema 校验与自定义 Schema 替换
- C++ 生成文件通过 libclang 解析

---

## License

MIT
