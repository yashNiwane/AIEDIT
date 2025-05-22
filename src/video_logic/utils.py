import os

def _parse_position(pos_param, main_clip_w, main_clip_h, status_label_config_func, warning_fg_color_val):
    simple_pos_keywords = ["center", "left", "right", "top", "bottom",
                           "top_left", "top_right", "bottom_left", "bottom_right"]
    if isinstance(pos_param, str) and pos_param in simple_pos_keywords:
        return pos_param

    if isinstance(pos_param, str) and pos_param.startswith("(") and pos_param.endswith(")"):
        try: # Try to eval if it's a string representation of a tuple
            pos_param = eval(pos_param)
        except:
            status_label_config_func(text=f"Warning: Could not parse position string '{pos_param}'. Using 'center'.", fg=warning_fg_color_val)
            return "center"

    if isinstance(pos_param, (tuple, list)) and len(pos_param) == 2:
        x_val, y_val = pos_param
        px_x, px_y = None, None

        # Parse X
        if isinstance(x_val, str):
            if x_val in ["left", "center", "right"]: px_x = x_val
            elif '%' in x_val: px_x = float(x_val.strip('%')) / 100.0 * main_clip_w
            else:
                try: px_x = float(x_val)
                except ValueError: pass
        elif isinstance(x_val, (int, float)): px_x = x_val

        # Parse Y
        if isinstance(y_val, str):
            if y_val in ["top", "center", "bottom"]: px_y = y_val
            elif '%' in y_val: px_y = float(y_val.strip('%')) / 100.0 * main_clip_h
            else:
                try: px_y = float(y_val)
                except ValueError: pass
        elif isinstance(y_val, (int, float)): px_y = y_val

        if px_x is not None and px_y is not None:
            return (px_x, px_y)

    status_label_config_func(text=f"Warning: Invalid position format '{pos_param}'. Using 'center'.", fg=warning_fg_color_val)
    return "center"
