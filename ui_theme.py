import streamlit as st


def inject_theme() -> None:
    st.markdown(
        """
        <style>

        /* ==================================================
           ASCENSION WARM LIGHT THEME
        ================================================== */

        :root {
            /* Page / surfaces */
            --ascension-bg: #F6F2EA;
            --ascension-surface: #FFFDFC;
            --ascension-surface-soft: #EFE9DF;

            /* Brand */
            --ascension-navy: #203A5C;
            --ascension-red: #A44942;
            --ascension-red-hover: #8F3E38;

            /* Text */
            --ascension-text: #3F4750;
            --ascension-text-soft: #505861;
            --ascension-text-quiet: #626A72;
            --ascension-label: #586A82;

            /* General borders */
            --ascension-border: #D8D0C5;
            --ascension-border-hover: #C7BEB2;

            /* Card borders */
            --ascension-card-border: #C5B9AA;
            --ascension-card-edge: #D9D0C4;

            /* Inputs */
            --ascension-input-bg: #2F3038;
            --ascension-input-border: #555761;
            --ascension-input-border-focus: #8B8D96;
            --ascension-input-text: #F4F1EC;
            --ascension-input-placeholder: #AEB0B7;
        }


        /* ==================================================
           PAGE
        ================================================== */

        html,
        body,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"] {
            background-color: var(--ascension-bg);
            color: var(--ascension-text);
        }

        [data-testid="stAppViewContainer"] {
            background:
                linear-gradient(
                    180deg,
                    #FAF7F1 0%,
                    var(--ascension-bg) 260px
                );
        }


        /* ==================================================
           TYPOGRAPHY
        ================================================== */

        h1,
        h2,
        h3,
        h4,
        h5,
        h6 {
            color: var(--ascension-navy) !important;
        }

        p,
        li,
        label,
        span {
            color: inherit;
        }

        [data-testid="stMarkdownContainer"] p {
            color: var(--ascension-text);
        }

        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] *,
        [data-testid="stCaptionContainer"] p {
            color: var(--ascension-text-soft) !important;
            opacity: 1 !important;
        }

        a {
            color: var(--ascension-navy);
        }


        /* ==================================================
           BORDERED CONTAINERS / CARDS
        ================================================== */

        /*
           Household and child cards.

           We deliberately force the edge instead of relying
           only on Streamlit's default border styling.
        */

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: var(--ascension-surface) !important;

            border:
                1px solid var(--ascension-card-border) !important;

            border-radius: 12px !important;

            box-shadow:
                inset 0 0 0 1px rgba(255, 255, 255, 0.65),
                0 1px 2px rgba(32, 58, 92, 0.05),
                0 3px 8px rgba(32, 58, 92, 0.035) !important;

            box-sizing: border-box !important;
        }


        /*
           Streamlit sometimes places the visible surface
           on the first child of the wrapper.
        */

        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            background-color: var(--ascension-surface) !important;
            border-radius: 11px !important;
        }


        /*
           Extra inset edge.

           This makes the card boundary remain visible even
           if Streamlit's own border styling changes.
        */

        div[data-testid="stVerticalBlockBorderWrapper"]::after {
            content: "";
            position: absolute;
            inset: 0;
            border-radius: 12px;
            box-shadow:
                inset 0 0 0 1px var(--ascension-card-edge);
            pointer-events: none;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            position: relative;
        }


        /* ==================================================
           DIVIDERS
        ================================================== */

        hr {
            border-color: var(--ascension-border) !important;
            opacity: 0.85;
        }


        /* ==================================================
           INPUT LABELS
        ================================================== */

        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] span,
        label,
        label p,
        label span {
            color: var(--ascension-text) !important;
            opacity: 1 !important;
        }


        /* ==================================================
           INPUTS
        ================================================== */

        [data-baseweb="input"] > div,
        [data-baseweb="textarea"] > div,
        [data-baseweb="select"] > div {
            background-color:
                var(--ascension-input-bg) !important;

            border:
                1px solid var(--ascension-input-border) !important;

            color:
                var(--ascension-input-text) !important;
        }


        /* Standard text inputs */

        [data-baseweb="input"] input,
        input {
            color:
                var(--ascension-input-text) !important;

            -webkit-text-fill-color:
                var(--ascension-input-text) !important;

            caret-color:
                var(--ascension-input-text) !important;
        }


        /* Text areas */

        [data-baseweb="textarea"] textarea,
        textarea {
            color:
                var(--ascension-input-text) !important;

            -webkit-text-fill-color:
                var(--ascension-input-text) !important;

            caret-color:
                var(--ascension-input-text) !important;
        }


        /* Placeholder text */

        [data-baseweb="input"] input::placeholder,
        [data-baseweb="textarea"] textarea::placeholder,
        input::placeholder,
        textarea::placeholder {
            color:
                var(--ascension-input-placeholder) !important;

            -webkit-text-fill-color:
                var(--ascension-input-placeholder) !important;

            opacity: 1 !important;
        }


        /* Select boxes */

        [data-baseweb="select"] span,
        [data-baseweb="select"] div {
            color:
                var(--ascension-input-text) !important;
        }

        [data-baseweb="select"] svg {
            fill:
                var(--ascension-input-text) !important;

            color:
                var(--ascension-input-text) !important;
        }


        /* Input icons */

        [data-baseweb="input"] svg,
        [data-baseweb="textarea"] svg {
            fill:
                var(--ascension-input-placeholder) !important;

            color:
                var(--ascension-input-placeholder) !important;
        }


        /* Focus state */

        [data-baseweb="input"]:focus-within > div,
        [data-baseweb="textarea"]:focus-within > div,
        [data-baseweb="select"]:focus-within > div {
            border-color:
                var(--ascension-input-border-focus) !important;

            box-shadow:
                0 0 0 1px
                var(--ascension-input-border-focus) !important;
        }


        /* Disabled */

        input:disabled,
        textarea:disabled {
            color: #C6C4C0 !important;
            -webkit-text-fill-color: #C6C4C0 !important;
            opacity: 0.75 !important;
        }


        /* ==================================================
           DATE INPUTS
        ================================================== */

        [data-testid="stDateInput"]
        [data-baseweb="input"] > div {
            background-color:
                var(--ascension-input-bg) !important;

            border-color:
                var(--ascension-input-border) !important;
        }

        [data-testid="stDateInput"] input {
            color:
                var(--ascension-input-text) !important;

            -webkit-text-fill-color:
                var(--ascension-input-text) !important;
        }

        [data-testid="stDateInput"] svg {
            color:
                var(--ascension-input-placeholder) !important;

            fill:
                var(--ascension-input-placeholder) !important;
        }


        /* ==================================================
           PRIMARY BUTTONS
        ================================================== */

        button[kind="primary"] {
            background-color:
                var(--ascension-red) !important;

            border-color:
                var(--ascension-red) !important;

            color: #FFFFFF !important;
            font-weight: 700;
        }

        button[kind="primary"],
        button[kind="primary"] *,
        button[kind="primary"] p,
        button[kind="primary"] span {
            color: #FFFFFF !important;

            -webkit-text-fill-color:
                #FFFFFF !important;
        }

        button[kind="primary"]:hover {
            background-color:
                var(--ascension-red-hover) !important;

            border-color:
                var(--ascension-red-hover) !important;

            color: #FFFFFF !important;
        }


        /* ==================================================
           SECONDARY BUTTONS
        ================================================== */

        button[kind="secondary"] {
            background-color:
                var(--ascension-surface) !important;

            border:
                1px solid var(--ascension-border) !important;

            color: #19375D !important;
        }

        button[kind="secondary"],
        button[kind="secondary"] *,
        button[kind="secondary"] p,
        button[kind="secondary"] span {
            color: #19375D !important;

            -webkit-text-fill-color:
                #19375D !important;
        }

        button[kind="secondary"]:hover {
            background-color:
                var(--ascension-surface-soft) !important;

            border-color:
                var(--ascension-border-hover) !important;

            color: #19375D !important;
        }


        /* ==================================================
           TERTIARY BUTTONS
        ================================================== */

        button[kind="tertiary"],
        button[kind="tertiary"] *,
        button[kind="tertiary"] p,
        button[kind="tertiary"] span {
            color: #234F7C !important;

            -webkit-text-fill-color:
                #234F7C !important;
        }


        /* ==================================================
           DATAFRAMES / TABLES
        ================================================== */

        [data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;

            border:
                1px solid var(--ascension-border);
        }


        /* ==================================================
           DIALOGS
        ================================================== */

        [data-testid="stDialog"] > div {
            background-color:
                var(--ascension-surface) !important;
        }

        [role="dialog"] {
            background-color:
                var(--ascension-surface) !important;

            color:
                var(--ascension-text) !important;
        }

        [role="dialog"] h1,
        [role="dialog"] h2,
        [role="dialog"] h3 {
            color:
                var(--ascension-navy) !important;
        }

        [role="dialog"] p {
            color:
                var(--ascension-text) !important;
        }


        /* ==================================================
           EXPANDERS
        ================================================== */

        [data-testid="stExpander"] {
            background-color:
                var(--ascension-surface);

            border:
                1px solid var(--ascension-border) !important;

            border-radius: 10px;
        }


        /* ==================================================
           METRICS
        ================================================== */

        [data-testid="stMetric"] {
            color: var(--ascension-text);
        }

        [data-testid="stMetricLabel"] {
            color: var(--ascension-text-soft);
        }

        [data-testid="stMetricValue"] {
            color: var(--ascension-navy);
        }


        /* ==================================================
           CODE / HOUSEHOLD ID
        ================================================== */

        code {
            background-color:
                var(--ascension-surface-soft) !important;

            color:
                var(--ascension-navy) !important;
        }


        /* ==================================================
           STREAMLIT STATUS BOXES
        ================================================== */

        [data-testid="stAlert"] {
            border-radius: 10px;
        }


        /* ==================================================
           EXISTING CUSTOM APP CLASSES
        ================================================== */

        /* Small labels / eyebrows */

        .landing-parish,
        .landing-section-label,
        .landing-admin,
        .section-eyebrow,
        .progress-label,
        .review-section-title,
        .review-field-label,
        .completion-kicker,
        .household-id-label {
            color:
                var(--ascension-label) !important;

            opacity: 1 !important;
        }


        /* Titles */

        .landing-title,
        .completion-title,
        .landing-action-title,
        .review-ready-title,
        .review-submit-title,
        .empty-state-title {
            color:
                var(--ascension-navy) !important;
        }


        /* Main explanatory copy */

        .landing-welcome,
        .landing-welcome *,
        .landing-action-description,
        .landing-action-description *,
        .registration-intro,
        .registration-intro *,
        .empty-state-copy,
        .empty-state-copy *,
        .review-submit-copy,
        .review-submit-copy *,
        .household-id-help,
        .household-id-help * {
            color: #47505A !important;
            opacity: 1 !important;
        }


        /* Quiet helper text */

        .landing-recovery,
        .landing-recovery *,
        .privacy-note,
        .privacy-note * {
            color:
                var(--ascension-text-quiet) !important;

            opacity: 1 !important;
        }


        /* Review values */

        .review-person-name,
        .review-child-name,
        .review-field-value {
            color:
                var(--ascension-text) !important;
        }


        /* ==================================================
           SIDEBAR
        ================================================== */

        [data-testid="stSidebar"] {
            background-color:
                var(--ascension-surface-soft);
        }


        /* ==================================================
           STREAMLIT HEADER
        ================================================== */

        [data-testid="stHeader"] {
            background-color: #0E1117;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )