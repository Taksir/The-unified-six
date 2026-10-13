from u6.split import last_narrator, segments, split_narration, strip_prophet_formula
from u6.textnorm import clean, letters, normalize


def sp(text):
    return split_narration(clean(text))


def test_companion_says_prophet_said():
    s = sp('حدثنا مسدد، حدثنا يحيى، عن شعبة، عن قتادة، عن أنس، قال قال رسول الله صلى الله عليه وسلم " لا يؤمن أحدكم حتى يحب لأخيه ما يحب لنفسه ".')
    assert letters(s.isnad).endswith("عن انس، قال")
    assert letters(s.matn).startswith("قال رسول الله")
    assert s.kind == "full" and s.tail == ""


def test_narrative_matn_after_qalat():
    s = sp("أخبرنا محمد بن عبد الأعلى، قال حدثنا خالد، عن عائشة، قالت كنت أغتسل أنا ورسول الله، صلى الله عليه وسلم من إناء واحد.")
    assert letters(s.matn).startswith("كنت اغتسل")


def test_an_prophet_starts_matn():
    s = sp("حدثنا قتيبة، حدثنا الليث، عن نافع، عن ابن عمر، أن رسول الله صلى الله عليه وسلم نهى عن بيع الولاء.")
    assert letters(s.matn).startswith("ان رسول الله")


def test_an_narrator_haddathahu_stays_in_isnad():
    s = sp("حدثنا أبو اليمان، أخبرنا شعيب، عن الزهري، قال أخبرني سعيد، أن أبا هريرة حدثه أن رسول الله صلى الله عليه وسلم قال \" تفضل صلاة الجميع \".")
    assert "حدثه" in letters(s.isnad)
    assert letters(s.matn).startswith("ان رسول الله")


def test_tahwil_and_resumed_chain():
    s = sp("حدثنا عبدان، قال أخبرنا عبد الله، عن الزهري، ح وحدثنا بشر بن محمد، قال أخبرنا يونس، ومعمر، عن الزهري، نحوه. قال أخبرني عبيد الله، عن ابن عباس، قال كان رسول الله صلى الله عليه وسلم أجود الناس.")
    assert letters(s.matn).startswith("كان رسول الله")
    assert s.kind == "full"  # "نحوه" inside the chain is not a back-reference


def test_tail_comment_and_secondary_chain():
    s = sp('حدثنا محمد بن بشار، حدثنا سفيان، عن أبي ذر، قال قال لي رسول الله صلى الله عليه وسلم " اتق الله حيثما كنت ". قال وفي الباب عن أبي هريرة. قال أبو عيسى هذا حديث حسن صحيح. حدثنا محمود، حدثنا وكيع، بهذا الإسناد نحوه.')
    assert "اتق الله" in s.matn and "في الباب" not in s.matn
    assert letters(s.tail).startswith("قال وفي الباب")
    assert s.kind == "full"


def test_back_reference():
    s = sp("وحدثناه أبو بكر بن أبي شيبة، حدثنا وكيع، عن سفيان، بهذا الإسناد مثله.")
    assert s.kind == "ref"
    s = sp('حدثناه يحيى بن يحيى، أخبرنا أبو معاوية، عن هشام بن عروة، بهذا الإسناد وزاد ثم قال " أما بعد فإن الشمس والقمر من آيات الله ". وزاد أيضا ثم رفع يديه فقال " اللهم هل بلغت ".')
    assert s.kind == "ref_variant"


def test_prophet_link_without_speech_verb():
    s = sp("حدثنا عبد الله بن يوسف، أخبرنا مالك، عن ابن شهاب، عن محمد بن جبير بن مطعم، عن أبيه، قال سمعت رسول الله صلى الله عليه وسلم قرأ في المغرب بالطور.")
    assert "بالطور" in s.matn


def test_dash_gloss_is_masked():
    s = sp("حدثنا هناد، حدثنا عبدة، عن محمد، - يعني ابن إسحاق - عن يزيد، عن ديلم، قال سألت رسول الله صلى الله عليه وسلم فقلت يا رسول الله إنا بأرض باردة.")
    assert "يعني ابن اسحاق" in letters(s.isnad)
    assert letters(s.matn).startswith("سالت")


def test_empty_and_segments_roundtrip():
    assert sp("").kind == "empty"
    text = clean('حدثنا مسدد، عن أنس، قال قال رسول الله صلى الله عليه وسلم " يسروا ". قال أبو داود هذا لفظه.')
    s = split_narration(text)
    assert segments(text, s.bounds) == (s.isnad, s.matn, s.tail)
    assert letters(s.tail).startswith("قال ابو داود")


def test_last_narrator():
    assert last_narrator(clean("حدثنا مسدد، حدثنا يحيى، عن شعبة، عن قتادة، عن أنس بن مالك رضي الله عنه، قال")) == "انس بن مالك"
    assert last_narrator(clean("حدثنا الحميدي، عن علقمة، يقول سمعت عمر بن الخطاب على المنبر، قال: سمعت رسول الله صلى الله عليه وسلم، يقول")) == "عمر بن الخطاب"
    assert last_narrator(clean("عن ابن بريدة، عن أبيه، عن النبي صلى الله عليه وسلم قال")) == "ابيه"


def test_strip_prophet_formula():
    assert strip_prophet_formula(normalize("قال رسول الله صلى الله عليه وسلم إنما الأعمال")) == "انما الاعمال"
    assert strip_prophet_formula(normalize("أنه سمع النبي صلى الله عليه وسلم يقول صلاة الجماعة")) == "صلاه الجماعه"
