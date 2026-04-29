# 模型文件元数据生成器完整实现计划

## Summary

从当前空仓库出发，实现 README 描述的完整工具链：Python/trimesh 解析 `.gltf/.glb`，生成 `.modelmeta.json`；支持单文件、glob 批量、纹理解包、Schema 驱动输出；再基于 Schema + `symbol_map.py` 生成 C++17 结构体与 nlohmann/json 序列化代码，并用 libclang 校验。

默认按“先稳定 JSON 元数据，再生成 C++ 代码”的顺序交付，避免 C++ 生成器依赖尚未稳定的数据结构。

## Key Changes

- 建立 Python 包结构：
  - `gltf_meta_generator.py` 作为 CLI 入口。
  - `modelmeta/gltf_reader.py` 负责读取 GLTF/GLB。
  - `modelmeta/metadata_builder.py` 负责构建元数据。
  - `modelmeta/texture_unpacker.py` 负责内嵌纹理解包。
  - `modelmeta/schema_loader.py` 负责 Schema 加载与校验。
  - `modelmeta/output_writer.py` 负责单文件和批量输出。
- 新增配置与映射：
  - `model_meta_configs.py` 提供默认配置，包括命名空间、命名规则、float 截断位数、默认输出路径、纹理解包配置。
  - `symbol_map.py` 维护 JSON 字段、Python 内部字段、C++ 类型/成员名之间的映射。
  - CLI 参数优先级高于配置文件。
- 新增 Schema：
  - `schema/modelmeta.schema.json` 定义 `model_type`、`bounding_box`、`model_part`、`skeleton`、`textures`、`material`。
  - JSON 输出先按内部标准字段生成，再经过 `symbol_map.py` 映射成最终字段。
  - README 中的 `bouding_box` 视为拼写错误，正式字段使用 `bounding_box`；如需要兼容旧字段，可在 `symbol_map.py` 中映射。
- 实现 CLI 行为：
  - `python gltf_meta_generator.py model.glb`
  - `python gltf_meta_generator.py model.glb -o output.json`
  - `python gltf_meta_generator.py "assets/**/*.glb" -o output_dir/`
  - `python gltf_meta_generator.py model.glb --unpack`
  - `python gltf_meta_generator.py model.glb --schema my_schema.json`
- 实现元数据提取：
  - `model_type`：检测 skins/joints/bones，存在骨架则为 `Skeletal`，否则为 `Static`。
  - `bounding_box`：输出 `{ "min": [x,y,z], "max": [x,y,z] }`。
  - `model_part`：每个 mesh/geometry 输出模型名、局部包围盒、材质信息。
  - `material`：输出材质名、PBR 标记、纹理槽、alpha 模式、roughness、metallic。
  - `textures`：汇总所有材质引用的纹理相对路径并去重。
  - `skeleton`：仅 Skeletal 模型输出，记录节点名及关联的 `model_part`。
- 实现纹理解包：
  - `--unpack` 时将 Data URI / BufferView 纹理导出到默认 `textures/`。
  - 文件名使用 `<模型名>_<纹理名或索引>.<ext>` 防冲突。
  - 元数据中的纹理槽改为相对 `.modelmeta.json` 的路径。
- 实现 C++ 生成：
  - `tools/schema_to_cpp.py` 从 Schema 生成 C++17 header。
  - `tools/cpp_json_codegen.py` 生成 nlohmann/json `from_json/to_json` 和 `Parse(std::string jsonStr)`。
  - 结构体按 Schema 依赖拓扑排序。
  - 类型映射：string -> `std::string`，number -> `float`，integer -> `int`，boolean -> `bool`，array -> `std::vector<T>`，object -> struct。
  - namespace、结构体名、成员名、函数名由 `model_meta_configs.py` 和 `symbol_map.py` 控制。
- 实现 libclang 校验：
  - Header 生成后调用 libclang 解析。
  - 校验失败时输出文件、行号、诊断信息。
  - `--sync existing.h` 读取已有 header，对比 Schema 后重写目标 header。

## Test Plan

- Python CLI：
  - 单文件 `.glb/.gltf` 默认输出到模型同级目录。
  - `-o output.json` 正确输出指定文件。
  - glob 模式要求 `-o` 为目录，并为每个模型生成 `<文件名>.modelmeta.json`。
  - 非法输入路径、空 glob、错误 `-o` 类型给出明确错误。
- 元数据正确性：
  - Static 模型输出 `model_type: "Static"`。
  - Skeletal 模型输出 `model_type: "Skeletal"` 和 `skeleton`。
  - 包围盒 min/max 为三元素 float 数组。
  - 材质 PBR、alpha、roughness、metallic、纹理槽正确提取。
  - `textures` 与 `material` 汇总去重。
- 纹理解包：
  - GLB 内嵌纹理导出到 `textures/`。
  - 输出文件名无冲突。
  - JSON 中纹理路径为相对路径。
- Schema：
  - 默认 `schema/modelmeta.schema.json` 校验通过。
  - `--schema my_schema.json` 能替换默认 Schema。
  - Schema 校验失败时输出可读错误。
- C++：
  - `schema_to_cpp.py` 能生成 C++17 header。
  - 生成文件通过 libclang 解析。
  - nlohmann/json 序列化代码可编译。
  - `Parse(std::string jsonStr)` 能从 `.modelmeta.json` 构造根结构体。

## Assumptions

- 依赖使用 `trimesh` 解析模型；如 trimesh 无法完整读取某些 GLTF 扩展，再补充 `pygltflib` 做底层 GLTF JSON/Buffer 解析。
- 正式 JSON 字段使用 `bounding_box`，不沿用 README 中的 `bouding_box` 拼写错误。
- 默认输出 JSON 使用 UTF-8、`indent=2`，并保持稳定字段顺序，方便 diff。
- C++ 目标标准为 C++17，JSON 后端固定为 nlohmann/json。
- libclang 是可选运行时依赖：未安装时 Python 元数据生成仍可用，C++ 校验命令给出明确安装提示。
