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

            /* Borders */
            --ascension-border: #D8D0C5;
            --ascension-border-hover: #C7BEB2;

            /* Light inputs */
            --ascension-input-bg: #FFFDFC;
            --ascension-input-bg-focus: #FFFFFF;
            --ascension-input-border: #CFC6BA;
            --ascension-input-border-focus: #7B8DA5;
            --ascension-input-text: #2F3D4D;
            --ascension-input-placeholder: #8A8580;
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
           CARDS / BORDERED CONTAINERS
        ================================================== */

        [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: var(--ascension-surface);
            border-color: var(--ascension-border) !important;
            border-radius: 12px;
        }


        /* ==================================================
           DIVIDERS
        ================================================== */

        hr {
            border-color: var(--ascension-border) !important;
            opacity: 0.85;
        }


        /* ==================================================
           WIDGET LABELS
        ================================================== */

        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] *,
        [data-testid="stWidgetLabel"] p,
        [data-testid="stWidgetLabel"] span {
            color: var(--ascension-text) !important;
            -webkit-text-fill-color: var(--ascension-text) !important;
            opacity: 1 !important;
        }


        /* ==================================================
           TEXT INPUTS
        ================================================== */

        /*
           Light field background + dark text.

           These selectors intentionally override the old
           dark-theme input colors.
        */

        [data-testid="stTextInput"] [data-baseweb="input"] > div,
        [data-testid="stNumberInput"] [data-baseweb="input"] > div,
        [data-baseweb="input"] > div {
            background-color: var(--ascension-input-bg) !important;
            border-color: var(--ascension-input-border) !important;
            color: var(--ascension-input-text) !important;
        }


        /* Actual entered text */

        [data-testid="stTextInput"] input,
        [data-testid="stNumberInput"] input,
        [data-baseweb="input"] input,
        input {
            color: var(--ascension-input-text) !important;

            -webkit-text-fill-color:
                var(--ascension-input-text) !important;

            caret-color: var(--ascension-navy) !important;

            opacity: 1 !important;
        }


        /* Placeholder text */

        [data-testid="stTextInput"] input::placeholder,
        [data-testid="stNumberInput"] input::placeholder,
        [data-baseweb="input"] input::placeholder,
        input::placeholder {
            color: var(--ascension-input-placeholder) !important;

            -webkit-text-fill-color:
                var(--ascension-input-placeholder) !important;

            opacity: 1 !important;
        }


        /* ==================================================
           TEXT AREAS
        ================================================== */

        [data-testid="stTextArea"] [data-baseweb="textarea"] > div,
        [data-baseweb="textarea"] > div {
            background-color: var(--ascension-input-bg) !important;
            border-color: var(--ascension-input-border) !important;
            color: var(--ascension-input-text) !important;
        }

        [data-testid="stTextArea"] textarea,
        [data-baseweb="textarea"] textarea,
        textarea {
            color: var(--ascension-input-text) !important;

            -webkit-text-fill-color:
                var(--ascension-input-text) !important;

            caret-color: var(--ascension-navy) !important;

            opacity: 1 !important;
        }

        [data-testid="stTextArea"] textarea::placeholder,
        [data-baseweb="textarea"] textarea::placeholder,
        textarea::placeholder {
            color: var(--ascension-input-placeholder) !important;

            -webkit-text-fill-color:
                var(--ascension-input-placeholder) !important;

            opacity: 1 !important;
        }


        /* ==================================================
           SELECT BOXES
        ================================================== */

        [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-baseweb="select"] > div {
            background-color: var(--ascension-input-bg) !important;
            border-color: var(--ascension-input-border) !important;
            color: var(--ascension-input-text) !important;
        }

        [data-testid="stSelectbox"] [data-baseweb="select"] span,
        [data-baseweb="select"] span {
            color: var(--ascension-input-text) !important;

            -webkit-text-fill-color:
                var(--ascension-input-text) !important;
        }

        [data-testid="stSelectbox"] svg,
        [data-baseweb="select"] svg {
            color: var(--ascension-text-soft) !important;
            fill: var(--ascension-text-soft) !important;
        }


        /* ==================================================
           DATE INPUTS
        ================================================== */

        [data-testid="stDateInput"] [data-baseweb="input"] > div {
            background-color: var(--ascension-input-bg) !important;
            border-color: var(--ascension-input-border) !important;
            color: var(--ascension-input-text) !important;
        }

        [data-testid="stDateInput"] input {
            color: var(--ascension-input-text) !important;

            -webkit-text-fill-color:
                var(--ascension-input-text) !important;

            caret-color: var(--ascension-navy) !important;

            opacity: 1 !important;
        }

        [data-testid="stDateInput"] input::placeholder {
            color: var(--ascension-input-placeholder) !important;

            -webkit-text-fill-color:
                var(--ascension-input-placeholder) !important;

            opacity: 1 !important;
        }

        [data-testid="stDateInput"] svg {
            color: var(--ascension-text-soft) !important;
            fill: var(--ascension-text-soft) !important;
        }


        /* ==================================================
           INPUT ICONS
        ================================================== */

        [data-baseweb="input"] svg,
        [data-baseweb="textarea"] svg {
            color: var(--ascension-text-soft) !important;
            fill: var(--ascension-text-soft) !important;
        }


        /* ==================================================
           INPUT FOCUS STATE
        ================================================== */

        [data-baseweb="input"]:focus-within > div,
        [data-baseweb="textarea"]:focus-within > div,
        [data-baseweb="select"]:focus-within > div {
            background-color:
                var(--ascension-input-bg-focus) !important;

            border-color:
                var(--ascension-input-border-focus) !important;

            box-shadow:
                0 0 0 1px
                var(--ascension-input-border-focus) !important;
        }


        /* ==================================================
           DISABLED INPUTS
        ================================================== */

        input:disabled,
        textarea:disabled {
            color: #77736E !important;

            -webkit-text-fill-color:
                #77736E !important;

            background-color: #F0EDE8 !important;
            opacity: 0.75 !important;
        }


        /* ==================================================
           PRIMARY BUTTONS
        ================================================== */

        button[kind="primary"] {
            background-color: var(--ascension-red) !important;
            border-color: var(--ascension-red) !important;
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
            background-color: var(--ascension-red-hover) !important;
            border-color: var(--ascension-red-hover) !important;
            color: #FFFFFF !important;
        }


        /* ==================================================
           SECONDARY BUTTONS
        ================================================== */

        button[kind="secondary"] {
            background-color: var(--ascension-surface) !important;
            border-color: var(--ascension-border) !important;
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
           DOWNLOAD BUTTONS
        ================================================== */

        [data-testid="stDownloadButton"] button,
        [data-testid="stDownloadButton"] button *,
        [data-testid="stDownloadButton"] button p,
        [data-testid="stDownloadButton"] button span {
            color: #19375D !important;

            -webkit-text-fill-color:
                #19375D !important;
        }


        /* ==================================================
           DATAFRAMES / TABLES
        ================================================== */

        [data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid var(--ascension-border);
        }


        /* ==================================================
           DIALOGS
        ================================================== */

        [data-testid="stDialog"] > div {
            background-color: var(--ascension-surface) !important;
        }

        [role="dialog"] {
            background-color: var(--ascension-surface) !important;
            color: var(--ascension-text) !important;
        }

        [role="dialog"] h1,
        [role="dialog"] h2,
        [role="dialog"] h3 {
            color: var(--ascension-navy) !important;
        }

        [role="dialog"] p {
            color: var(--ascension-text) !important;
        }


        /* ==================================================
           EXPANDERS
        ================================================== */

        [data-testid="stExpander"] {
            background-color: var(--ascension-surface);
            border-color: var(--ascension-border) !important;
            border-radius: 10px;
        }


        /* ==================================================
           METRICS
        ================================================== */

        [data-testid="stMetric"] {
            color: var(--ascension-text);
        }

        [data-testid="stMetricLabel"],
        [data-testid="stMetricLabel"] * {
            color: var(--ascension-text-soft) !important;
        }

        [data-testid="stMetricValue"],
        [data-testid="stMetricValue"] * {
            color: var(--ascension-navy) !important;
        }


        /* ==================================================
           CODE / HOUSEHOLD ID
        ================================================== */

        code {
            background-color: var(--ascension-surface-soft) !important;
            color: var(--ascension-navy) !important;
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


        /* --------------------------------------------------
           LABELS / EYEBROWS
        -------------------------------------------------- */

        .landing-parish,
        .landing-section-label,
        .landing-admin,
        .section-eyebrow,
        .progress-label,
        .review-section-title,
        .review-field-label,
        .completion-kicker,
        .household-id-label {
            color: var(--ascension-label) !important;
            opacity: 1 !important;
        }


        /* --------------------------------------------------
           TITLES
        -------------------------------------------------- */

        .landing-title,
        .completion-title,
        .landing-action-title,
        .review-ready-title,
        .review-submit-title,
        .empty-state-title,
        .progress-title,
        .next-steps-title {
            color: var(--ascension-navy) !important;
        }


        /* --------------------------------------------------
           MAIN BODY / EXPLANATORY COPY
        -------------------------------------------------- */

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
        .household-id-help *,
        .completion-copy,
        .completion-copy * {
            color: #47505A !important;
            opacity: 1 !important;
        }


        /* --------------------------------------------------
           QUIET HELPER TEXT
        -------------------------------------------------- */

        .landing-recovery,
        .landing-recovery *,
        .privacy-note,
        .privacy-note *,
        .completion-footer,
        .completion-footer * {
            color: var(--ascension-text-quiet) !important;
            opacity: 1 !important;
        }


        /* --------------------------------------------------
           REVIEW VALUES
        -------------------------------------------------- */

        .review-person-name,
        .review-child-name,
        .review-field-value,
        .review-check,
        .next-step {
            color: var(--ascension-text) !important;
        }


        /* --------------------------------------------------
           PROGRESS STATES
        -------------------------------------------------- */

        .progress-complete,
        .progress-needed {
            color: var(--ascension-text) !important;
        }

        .progress-waiting {
            color: var(--ascension-text-soft) !important;
            opacity: 1 !important;
        }


        /* ==================================================
           SIDEBAR
        ================================================== */

        [data-testid="stSidebar"] {
            background-color: var(--ascension-surface-soft);
        }


        /* ==================================================
           STREAMLIT HEADER
        ================================================== */

        [data-testid="stHeader"] {
            background-color: transparent;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )