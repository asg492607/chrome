class BoxModel:
    @staticmethod
    def parse_px(val_str, default=0):
        if not val_str:
            return default
        try:
            return int(val_str.replace("px", "").replace("pt", "").strip())
        except:
            return default

    @staticmethod
    def compute_margins(style, avail_width):
        m_top = BoxModel.parse_px(style.get("margin-top"), 0)
        m_bottom = BoxModel.parse_px(style.get("margin-bottom"), 10)
        m_left = BoxModel.parse_px(style.get("margin-left"), 0)
        m_right = BoxModel.parse_px(style.get("margin-right"), 0)
        
        block_w = style.get("width")
        if block_w:
            block_w_px = BoxModel.parse_px(block_w, avail_width)
            if style.get("margin-left") == "auto" and style.get("margin-right") == "auto":
                m_left = (avail_width - block_w_px) // 2
                m_right = m_left
            elif style.get("margin-left") == "auto":
                m_left = avail_width - block_w_px - m_right
            elif style.get("margin-right") == "auto":
                m_right = avail_width - block_w_px - m_left
        else:
            block_w_px = avail_width - m_left - m_right
            
        return m_top, m_bottom, m_left, m_right, block_w_px

    @staticmethod
    def compute_padding(style):
        p_top = BoxModel.parse_px(style.get("padding-top"), 0)
        p_bottom = BoxModel.parse_px(style.get("padding-bottom"), 0)
        p_left = BoxModel.parse_px(style.get("padding-left"), 0)
        p_right = BoxModel.parse_px(style.get("padding-right"), 0)
        return p_top, p_bottom, p_left, p_right
