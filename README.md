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
- **命名风格**：通过 `naming_converter.py` 支持 `BigCamel` / `smallCamel` / `snake` / `SCREAMING` 命名风格转换。

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

参数通过编辑 `model_meta_configs.py` 中的 `ModelMetaConfig` 配置，或通过 CLI 参数传入。两步各自可独立运行，也可通过 `gltf_model_meta.py` 统一编排执行全部步骤。

```bash
# 只生成 .modelmeta.json（使用配置文件中的设置）
python gltf_meta_generator.py

# 运行全部三步（GLTF → JSON + C++ Header + C++ Source），可通过 CLI 覆盖配置
python gltf_model_meta.py --glob-patterns "assets/**/*.glb" --cpp-header-output include/modelmeta.h --cpp-source-output src/modelmeta.cpp
```

### 配置选项（`model_meta_configs.py`）

| 参数                 | 说明                                                                                           |
| -------------------- | ---------------------------------------------------------------------------------------------- |
| `glob_patterns`      | 输入文件匹配模式列表，默认 `["assets/**/*"]`。接受多个 glob 或具体文件路径                     |
| `output_path`        | 输出路径。`None`（默认）时在模型文件同级目录就地生成 `.modelmeta.json`；指定路径时输出到该路径 |
| `unpack_textures`    | 是否提取内嵌纹理，默认 `True`                                                                  |
| `texture_output_dir` | 纹理解包输出目录，默认 `"textures"`（相对于 `.modelmeta.json` 输出文件的父目录）               |
| `schema_path`        | JSON Schema 路径，默认 `schema/modelmeta.schema.json`                                          |
| `float_precision`    | 浮点数截断位数，`None` 表示不截断，默认 `6`                                                    |
| `namespace`          | C++ 命名空间，默认 `None`                                                                      |
| `type_naming`        | 类型命名风格：`BigCamel` / `smallCamel` / `snake` / `SCREAMING`，默认 `"BigCamel"`             |
| `member_naming`      | 成员变量命名风格，默认 `"snake"`                                                               |
| `enum_naming`        | 枚举值命名风格，默认 `"BigCamel"`                                                              |
| `function_naming`    | 函数签名命名风格，默认 `"BigCamel"`                                                            |
| `root_cpp_type`      | 根 C++ 类型名，默认 `"ModelMeta"`                                                              |
| `parse_function`     | 解析函数名，默认 `"Parse"`                                                                     |
| `cpp_header_output`  | C++ 头文件输出路径，默认 `include/modelmeta.h`                                                 |
| `cpp_source_output`  | C++ 源文件输出路径，默认 `src/modelmeta.cpp`                                                   |
| `header_include`     | C++ 源文件中引用的头文件路径，默认 `"modelmeta.h"`                                             |

### CLI 参数

所有配置项均可通过 CLI 参数覆盖（由 `gltf_model_meta.py` 解析）：

```bash
python gltf_model_meta.py --glob-patterns "assets/**/*.glb" \
    --cpp-header-output include/modelmeta.h \
    --cpp-source-output src/modelmeta.cpp \
    --unpack-textures --float-precision 6
```

### 默认行为

- `output_path` 未指定时：在模型文件所在目录就地生成 `textures/` 和 `<模型名>.modelmeta.json`
- `glob_patterns` 为空时：脚本报错退出

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

| 字段           | 说明                                                   |
| -------------- | ------------------------------------------------------ |
| `model_type`   | `"Skeletal"`（含骨架）或 `"Static"`                    |
| `bounding_box` | 整体包围盒，`{ min: float3, max: float3 }`             |
| `model_part`   | 模型部件数组，含名称、局部包围盒、材质                 |
| `material`     | PBR 材质信息：名称、纹理槽、透明度模式、粗糙度、金属度 |
| `skeleton`     | 骨架节点层级（仅 Skeletal 模型输出）                   |
| `textures`     | 所有材质引用的纹理路径汇总（去重）                     |
| `material`     | 所有材质名称汇总（去重）                               |

---

## C++ 代码生成

基于同一套 JSON Schema，可同步生成 C++17 结构体与 `nlohmann/json` 序列化代码。

### 生成头文件

```bash
# 通过配置运行（使用 model_meta_configs.py 中的 DEFAULT_CONFIG）
python tools/schema_to_cpp.py

# 通过主入口运行并覆盖输出路径
python gltf_model_meta.py --cpp-header-output include/modelmeta.h
```

- 结构体按依赖关系**拓扑排序**，无需手动调整顺序。
- 生成后自动调用 **libclang** 校验（可通过 `--skip-clang` 跳过），确保语法合法。
- 支持 `--namespace dc::meta` 自定义命名空间。

### 生成序列化实现

```bash
python tools/cpp_json_codegen.py
# 或通过主入口
python gltf_model_meta.py --cpp-source-output src/modelmeta.cpp --header-include modelmeta.h
```

暴露接口：

```cpp
auto meta = Parse(jsonString);  // 返回根结构体对象
```

### 同步已有头文件

设置 `schema_to_cpp_sync_path` 可将生成的头文件同步拷贝到另一位置：

```bash
python gltf_model_meta.py --schema-to-cpp-sync-path path/to/existing/modelmeta.h
```

### CMake 集成

使用 `add_custom_command` 在构建时自动生成 C++ 文件：

```cmake
set(MODELMETA_GLOB   "assets/**/*.glb")
set(MODELMETA_HEADER "${CMAKE_CURRENT_BINARY_DIR}/modelmeta.h")
set(MODELMETA_SOURCE "${CMAKE_CURRENT_BINARY_DIR}/modelmeta.cpp")

add_custom_command(
    OUTPUT  ${MODELMETA_HEADER} ${MODELMETA_SOURCE}
    COMMAND ${Python3_EXECUTABLE} "${CMAKE_SOURCE_DIR}/gltf_model_meta.py"
            --glob-patterns      "${MODELMETA_GLOB}"
            --cpp-header-output  "${MODELMETA_HEADER}"
            --cpp-source-output  "${MODELMETA_SOURCE}"
    DEPENDS ${CMAKE_SOURCE_DIR}/schema/modelmeta.schema.json
    COMMENT "Generating model-meta C++ sources"
)
```

---

## 项目结构

```
├── gltf_model_meta.py           # 主入口，编排三步流程
├── gltf_meta_generator.py       # 步骤1: GLTF/GLB → .modelmeta.json
├── model_meta_configs.py        # 统一配置（命名空间、命名规则、精度等）
├── naming_converter.py          # 命名风格转换（snake/BigCamel/smallCamel/SCREAMING）
├── symbol_map.py                # JSON / C++ 字段与符号映射表
├── schema/
│   └── modelmeta.schema.json    # 元数据 JSON Schema
├── modelmeta/
│   ├── gltf_reader.py           # GLTF/GLB 读取
│   ├── metadata_builder.py      # 构建元数据字典
│   ├── texture_unpacker.py      # 内嵌纹理解包
│   ├── schema_loader.py         # Schema 加载与校验
│   └── output_writer.py         # 输出路径解析与文件写入
├── tools/
│   ├── schema_to_cpp.py         # 步骤2: C++ Header 生成器
│   ├── cpp_json_codegen.py      # 步骤3: nlohmann/json 序列化代码生成器
│   └── cpp_schema.py            # C++ 类型与结构建模
└── .verify/                     # 验证用样本与输出参考
```

---

## 数据流概览

gltf_model_meta.main(argv) ← 有 CLI 解析
├─ step_gltf(config) → gltf_meta_generator: GLTF → .modelmeta.json
│ ├─ load_model() → ModelDocument
│ ├─ unpack_embedded_textures()
│ ├─ build_metadata() → dict
│ ├─ apply_json_field_mapping() (from symbol_map.py)
│ ├─ load_schema() → validate_metadata()
│ └─ write_metadata()
├─ step_schema_to_cpp(config) → schema_to_cpp: Schema → .h
│ ├─ build_structs() → topological_sort()
│ ├─ render_header() → validate_with_clang()
│ └─ write + optional sync
└─ step_cpp_json_codegen(config) → cpp_json_codegen: Schema → .cpp
└─ render_cpp() → to_json/from_json + Parse()

---

## 对外开放接口

- gltf_model_meta.main(argv) — CLI 总入口
- gltf_meta_generator.main(config) — 程序化调用元数据生成
- gltf_meta_generator.generate_for_file(path, is_glob, config) — 单文件生成
- symbol_map.json_field()/cpp_type()/cpp_member()/... — 字段映射查询
- naming_converter.convert_name(name, style) — 命名风格转换
- modelmeta.**init**.**version** = "0.1.0"

---

## 内部接口

- modelmeta/gltf_reader.load_model() → ModelDocument
- modelmeta/metadata*builder.build_metadata() + 17 个 * 前缀辅助函数
- modelmeta/texture*unpacker.unpack_embedded_textures() + 4 个 * 辅助函数
- modelmeta/schema_loader.load_schema() / validate_metadata()
- modelmeta/output_writer.iter_input_files() / resolve_output_path() / write_metadata()
- tools/cpp_schema.build_structs() / topological_sort() / cpp_type_for_schema()
- tools/schema_to_cpp.render_header() / render_enum() / validate_with_clang()
- tools/cpp_json_codegen.render_cpp() / render_to_json() / render_from_json()

---

只有 `gltf_model_meta.py` 解析 CLI 参数（通过 `model_meta_configs.py` 中的 `build_argparser()`），共 23 个标志：

| CLI 标志 | 类型 | 对应步骤 | 默认值 |
|---|---|---|---|
| `--glob-patterns` | `str[]` | Step 1 | `["assets/**/*"]` |
| `--output-path` | `Path` | Step 1 | `None` |
| `--unpack-textures` / `--no-unpack-textures` | `bool` | Step 1 | `True` |
| `--texture-output-dir` | `str` | Step 1 | `"textures"` |
| `--float-precision` | `int` | Step 1 | `6` |
| `--schema-path` | `Path` | 全部 | `schema/modelmeta.schema.json` |
| `--namespace` | `str` | Step 2/3 | `None` |
| `--type-naming` | `str` | Step 2/3 | `"BigCamel"` |
| `--member-naming` | `str` | Step 2/3 | `"snake"` |
| `--enum-naming` | `str` | Step 2/3 | `"BigCamel"` |
| `--function-naming` | `str` | Step 2/3 | `"BigCamel"` |
| `--root-cpp-type` | `str` | Step 2/3 | `"ModelMeta"` |
| `--parse-function` | `str` | Step 2/3 | `"Parse"` |
| `--cpp-header-output` | `Path` | Step 2 | `include/modelmeta.h` |
| `--cpp-source-output` | `Path` | Step 3 | `src/modelmeta.cpp` |
| `--header-include` | `str` | Step 3 | `"modelmeta.h"` |
| `--pch-output` | `Path` | Step 2 | `include/pch.h` |
| `--debug-yaml` | `Path` | Step 2 | `None` |
| `--module-name` | `str` | Step 2 | `"modelmeta"` |
| `--additional-includes` | `str[]` | Step 2 | `[]` |
| `--pch-includes` | `str[]` | Step 2 | `[]` |
| `--schema-to-cpp-sync-path` | `Path` | Step 2 | `None` |
| `--skip-clang` | `bool` | Step 2 | `False` |

其他三个脚本（`gltf_meta_generator.py`、`tools/schema_to_cpp.py`、`tools/cpp_json_codegen.py`）均**无 CLI 解析**，只能通过 `config` 对象程序化调用或依赖 `DEFAULT_CONFIG` 运行。

---

## 配置与自定义

编辑 `model_meta_configs.py` 可调整：

| 配置项               | 说明                                                              |
| -------------------- | ----------------------------------------------------------------- |
| `namespace`          | C++ 命名空间，如 `"dc::meta"` 或 `None`（默认）                   |
| `type_naming`        | 结构体命名风格：`BigCamel` / `smallCamel` / `snake` / `SCREAMING` |
| `member_naming`      | 成员变量命名风格                                                  |
| `float_precision`    | 浮点数截断位数，`None` 表示不截断，默认 `6`                       |
| `unpack_textures`    | 默认是否解包纹理，默认 `True`                                     |
| `texture_output_dir` | 默认纹理输出目录，默认 `"textures"`                               |
| `glob_patterns`      | 默认输入文件匹配模式列表，默认 `["assets/**/*"]`                  |

编辑 `symbol_map.py` 可重命名输出 JSON 字段或生成的 C++ 符号，而无需修改元数据提取逻辑。

---

## 验证

`.verify/` 目录包含参考样本与期望输出，可用于手动回归验证：

- 单文件 / glob 批量输出
- `Static` / `Skeletal` 模型类型识别
- 包围盒、材质、纹理、骨架字段正确性
- 纹理解包路径与文件名冲突处理
- Schema 校验与自定义 Schema 替换
- C++ 生成文件通过 libclang 解析

---

## License

MIT
