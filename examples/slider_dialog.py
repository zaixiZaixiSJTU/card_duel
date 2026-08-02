import FreeSimpleGUI as sg

# 定义范围

a = 1  # 最小值
b = 3  # 最大值
layout = [
    [sg.Text(f"燃烧的血量({a}-{b}):", text_color="red", font=("Song", 14, "bold"))],
    [
        sg.Slider(
            range=(a, b),
            default_value=a,
            orientation="h",
            key="-SLIDER-",
            enable_events=True,
        )
    ],
    [sg.Button("确定")],
]

window = sg.Window("代价", layout)
current_value = 1
while True:
    event, values = window.read()
    if event == sg.WIN_CLOSED:
        break
    if event == "-SLIDER-":
        current_value = int(values["-SLIDER-"])  # 确保是整数
    # 实时更新显示
    if event == "确定":
        sg.popup(f"当前值: {current_value}")
        break

window.close()
