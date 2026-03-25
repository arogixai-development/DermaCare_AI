"""
Test Dataset - DermaCare AI
==========================
20+ diverse skin condition test cases for AI validation.
"""
TEST_CASES = [
    {
        "id": "TC001",
        "name": "Lip Ulcer - Young Adult",
        "complaint": "Painful ulcer on lower lip for 3 weeks",
        "lesion": "Single deep ulcer with rolled borders on lower lip, 1.5cm diameter",
        "symptoms": "Painful when eating, slight bleeding, no fever",
        "patient_age": 28,
        "geographic_region": "Urban",
        "expected_keywords": ["ulcer", "lip", "oral", "aphthous", "herpes", "stomatitis"],
        "expected_diagnoses": ["Aphthous Stomatitis", "Herpes", "Traumatic Ulcer"]
    },
    {
        "id": "TC002",
        "name": "Hand Rash - Tropical",
        "complaint": "Itchy red rash on hands for 2 weeks",
        "lesion": "Erythematous vesicular patches on dorsal hands with oozing",
        "symptoms": "Intense itching worse at night, burning sensation",
        "patient_age": 35,
        "geographic_region": "Tropical",
        "expected_keywords": ["dermatitis", "eczema", "vesicular", "hand"],
        "expected_diagnoses": ["Contact Dermatitis", "Dyshidrotic Eczema", "Tinea"]
    },
    {
        "id": "TC003",
        "name": "Facial Rash - Middle Age",
        "complaint": "Butterfly-shaped rash on face for 1 month",
        "lesion": "Erythematous, scaly plaques across cheeks and nose bridge",
        "symptoms": "Photosensitivity, mild itching, fatigue",
        "patient_age": 42,
        "geographic_region": "Suburban",
        "expected_keywords": ["butterfly", "lupus", "malar", "rosacea", "facial"],
        "expected_diagnoses": ["Lupus Erythematosus", "Rosacea", "Seborrheic Dermatitis"]
    },
    {
        "id": "TC004",
        "name": "Leg Ulcer - Elderly",
        "complaint": "Non-healing wound on lower leg for 6 weeks",
        "lesion": "Shallow ulcer with irregular borders, surrounding hyperpigmentation",
        "symptoms": "Mild pain, swelling in ankles, history of varicose veins",
        "patient_age": 68,
        "geographic_region": "Rural",
        "expected_keywords": ["leg", "ulcer", "venous", "arterial", "diabetic"],
        "expected_diagnoses": ["Venous Stasis Ulcer", "Arterial Insufficiency", "Diabetic Ulcer"]
    },
    {
        "id": "TC005",
        "name": "Acne - Teenager",
        "complaint": "Pimples and blackheads on face for 3 months",
        "lesion": "Multiple comedones, papules, and pustules on forehead and cheeks",
        "symptoms": "Oily skin, occasional scarring, embarrassment",
        "patient_age": 16,
        "geographic_region": "Urban",
        "expected_keywords": ["acne", "comedones", "papules", "pustules", "face"],
        "expected_diagnoses": ["Acne Vulgaris", "Rosacea", "Folliculitis"]
    },
    {
        "id": "TC006",
        "name": "Ringworm - Child",
        "complaint": "Circular itchy rash on scalp",
        "lesion": "Well-defined circular patch with central clearing, scaling border",
        "symptoms": "Itching, hair loss in patch area",
        "patient_age": 8,
        "geographic_region": "Rural",
        "expected_keywords": ["ringworm", "tinea", "circular", "scalp", "fungal"],
        "expected_diagnoses": ["Tinea Capitis", "Alopecia Areata", "Seborrheic Dermatitis"]
    },
    {
        "id": "TC007",
        "name": "Eczema - Infant",
        "complaint": "Red, dry, itchy patches on baby's cheeks",
        "lesion": "Erythematous, dry, scaly patches on cheeks and outer arms",
        "symptoms": "Intense itching, especially at night, family history of allergies",
        "patient_age": 1,
        "geographic_region": "Urban",
        "expected_keywords": ["eczema", "atopic", "infant", "dry", "itchy"],
        "expected_diagnoses": ["Atopic Dermatitis", "Seborrheic Dermatitis", "Contact Dermatitis"]
    },
    {
        "id": "TC008",
        "name": "Psoriasis - Adult",
        "complaint": "Silvery scaly patches on elbows and knees",
        "lesion": "Well-demarcated erythematous plaques with silvery scale on extensor surfaces",
        "symptoms": "Mild itching, joint pain, nail changes",
        "patient_age": 45,
        "geographic_region": "Temperate",
        "expected_keywords": ["psoriasis", "silvery", "scale", "plaques", "elbows"],
        "expected_diagnoses": ["Psoriasis Vulgaris", "Seborrheic Dermatitis", "Lichen Planus"]
    },
    {
        "id": "TC009",
        "name": "Shingles - Elderly",
        "complaint": "Painful blistering rash on one side of torso",
        "lesion": "Grouped vesicles on erythematous base in dermatomal distribution, T5-T6",
        "symptoms": "Burning pain preceding rash, fever, malaise",
        "patient_age": 65,
        "geographic_region": "Suburban",
        "expected_keywords": ["shingles", "herpes", "vesicles", "dermatomal", "painful"],
        "expected_diagnoses": ["Herpes Zoster", "Contact Dermatitis", "Impetigo"]
    },
    {
        "id": "TC010",
        "name": "Melanoma Suspicion",
        "complaint": "Changing mole on back",
        "lesion": "Asymmetric pigmented lesion, 8mm, irregular borders, multiple colors",
        "symptoms": "Itching, bleeding, recent change in appearance",
        "patient_age": 55,
        "geographic_region": "Tropical",
        "expected_keywords": ["melanoma", "mole", "pigmented", "asymmetric", "cancer"],
        "expected_diagnoses": ["Melanoma", "Dysplastic Nevus", "Seborrheic Keratosis"]
    },
    {
        "id": "TC011",
        "name": "Contact Dermatitis",
        "complaint": "Red itchy rash where watchband was worn",
        "lesion": "Well-demarcated erythematous patch matching watchband shape",
        "symptoms": "Intense itching, burning, blistering in pattern",
        "patient_age": 38,
        "geographic_region": "Urban",
        "expected_keywords": ["contact", "dermatitis", "allergic", "pattern", "watch"],
        "expected_diagnoses": ["Allergic Contact Dermatitis", "Irritant Contact Dermatitis", "Cellulitis"]
    },
    {
        "id": "TC012",
        "name": "Cellulitis",
        "complaint": "Rapidly spreading red, swollen leg",
        "lesion": "Diffuse erythema, warmth, edema of left lower leg",
        "symptoms": "Fever, pain, chills, elevated white blood cell count",
        "patient_age": 52,
        "geographic_region": "Rural",
        "expected_keywords": ["cellulitis", "erythema", "warmth", "swelling", "infection"],
        "expected_diagnoses": ["Cellulitis", "DVT", "Erysipelas"]
    },
    {
        "id": "TC013",
        "name": "Vitiligo",
        "complaint": "White patches appearing on hands and face",
        "lesion": "Depigmented macules with well-defined borders on hands, face, and knees",
        "symptoms": "Asymptomatic, gradual spreading, family history of autoimmune",
        "patient_age": 30,
        "geographic_region": "Temperate",
        "expected_keywords": ["vitiligo", "depigmented", "white", "autoimmune"],
        "expected_diagnoses": ["Vitiligo", "Pityriasis Alba", "Tinea Versicolor"]
    },
    {
        "id": "TC014",
        "name": "Impetigo",
        "complaint": "Honey-crusted sores around nose in child",
        "lesion": "Golden-yellow crusted lesions around nostrils and mouth",
        "symptoms": "Mild itching, spread to other family members",
        "patient_age": 6,
        "geographic_region": "Urban",
        "expected_keywords": ["impetigo", "honey", "crusted", "bacterial", "contagious"],
        "expected_diagnoses": ["Impetigo", "Ecthyma", "Herpes Simplex"]
    },
    {
        "id": "TC015",
        "name": "Dermatitis Herpetiformis",
        "complaint": "Extremely itchy blisters on elbows and knees",
        "lesion": "Grouped vesicles and papules on extensor surfaces",
        "symptoms": "Intensely pruritic, symmetric distribution, associated with celiac disease",
        "patient_age": 35,
        "geographic_region": "Suburban",
        "expected_keywords": ["herpetiformis", "celiac", "pruritic", "blisters", "gluten"],
        "expected_diagnoses": ["Dermatitis Herpetiformis", "Bullous Pemphigoid", "Scabies"]
    },
    {
        "id": "TC016",
        "name": "Tinea Versicolor",
        "complaint": "Spotted skin discoloration on chest and back",
        "lesion": "Hypopigmented and hyperpigmented macules on trunk",
        "symptoms": "Usually asymptomatic, worse after sun exposure",
        "patient_age": 25,
        "geographic_region": "Tropical",
        "expected_keywords": ["tinea", "versicolor", "fungus", "trunk", "discoloration"],
        "expected_diagnoses": ["Tinea Versicolor", "Pityriasis Rosea", "Vitiligo"]
    },
    {
        "id": "TC017",
        "name": "Scabies",
        "complaint": "Intense itching all over body, worse at night",
        "lesion": "Burrows in web spaces, papules on wrists, ankles, waistline",
        "symptoms": "Severe nocturnal pruritus, household members affected",
        "patient_age": 28,
        "geographic_region": "Urban",
        "expected_keywords": ["scabies", "burrows", "pruritus", "mites", "contagious"],
        "expected_diagnoses": ["Scabies", "Dermatitis", "Prurigo"]
    },
    {
        "id": "TC018",
        "name": "Seborrheic Dermatitis",
        "complaint": "Flaky scalp and eyebrows",
        "lesion": "Greasy, yellowish scales on scalp, eyebrows, nasolabial folds",
        "symptoms": "Dandruff, mild itching, flaking",
        "patient_age": 40,
        "geographic_region": "Temperate",
        "expected_keywords": ["seborrheic", "dandruff", "scaly", "scalp", "flakes"],
        "expected_diagnoses": ["Seborrheic Dermatitis", "Psoriasis", "Tinea Capitis"]
    },
    {
        "id": "TC019",
        "name": "Lichen Planus",
        "complaint": "Purple flat bumps on wrists and ankles",
        "lesion": "Violaceous, polygonal, flat-topped papules on wrists and ankles",
        "symptoms": "Pruritic, oral involvement, nail changes",
        "patient_age": 48,
        "geographic_region": "Suburban",
        "expected_keywords": ["lichen", "planus", "purple", "polygonal", "itchy"],
        "expected_diagnoses": ["Lichen Planus", "Lupus", "Graft vs Host Disease"]
    },
    {
        "id": "TC020",
        "complaint": "White spots on child's face",
        "lesion": "Well-defined hypopigmented macules on cheeks",
        "symptoms": "Asymptomatic, recent swimming pool exposure",
        "patient_age": 10,
        "geographic_region": "Tropical",
        "expected_keywords": ["pityriasis", "alba", "hypopigmented", "child", "pool"],
        "expected_diagnoses": ["Pityriasis Alba", "Tinea Versicolor", "Vitiligo"]
    },
    {
        "id": "TC021",
        "name": "Hidradenitis Suppurativa",
        "complaint": "Recurrent painful lumps in armpits and groin",
        "lesion": "Deep tender nodules, abscesses, sinus tracts in axillae and groin",
        "symptoms": "Chronic, relapsing, scarring, foul-smelling discharge",
        "patient_age": 32,
        "geographic_region": "Urban",
        "expected_keywords": ["hidradenitis", "suppurativa", "abscesses", "sinus", "chronic"],
        "expected_diagnoses": ["Hidradenitis Suppurativa", "Folliculitis", "Furunculosis"]
    },
    {
        "id": "TC022",
        "name": "Pemphigus Vulgaris",
        "complaint": "Painful blisters in mouth and on skin",
        "lesion": "Flaccid bullae and erosions in oral mucosa and scalp",
        "symptoms": "Painful mouth ulcers, easy skin blistering, positive Nikolsky sign",
        "patient_age": 55,
        "geographic_region": "Temperate",
        "expected_keywords": ["pemphigus", "bullae", "erosions", "oral", "autoimmune"],
        "expected_diagnoses": ["Pemphigus Vulgaris", "Bullous Pemphigoid", "Herpes"]
    },
    {
        "id": "TC023",
        "name": "Erythema Multiforme",
        "complaint": "Target-like spots on hands and feet",
        "lesion": "Target lesions with three zones on palms, soles, and extremities",
        "symptoms": "Mild itching, preceding herpes infection, symmetric",
        "patient_age": 22,
        "geographic_region": "Suburban",
        "expected_keywords": ["multiforme", "target", "herpes", "extremities", "iris"],
        "expected_diagnoses": ["Erythema Multiforme", "Stevens-Johnson", "Urticaria"]
    },
    {
        "id": "TC024",
        "name": "Basal Cell Carcinoma",
        "complaint": "Pearly bump with visible blood vessels on nose",
        "lesion": "Nodular pearly papule with telangiectasias on left ala nasi",
        "symptoms": "Non-healing, occasional bleeding, sun-exposed area",
        "patient_age": 60,
        "geographic_region": "Tropical",
        "expected_keywords": ["basal", "carcinoma", "pearly", "telangiectasia", "cancer"],
        "expected_diagnoses": ["Basal Cell Carcinoma", "Squamous Cell Carcinoma", "Sebaceous Cyst"]
    },
    {
        "id": "TC025",
        "name": "Urticaria",
        "complaint": "Itchy raised welts all over body",
        "lesion": "Transient, raised, erythematous wheals of varying sizes",
        "symptoms": "Severe itching, lesions change location within hours, possible allergy trigger",
        "patient_age": 35,
        "geographic_region": "Urban",
        "expected_keywords": ["urticaria", "wheals", "hives", "allergic", "transient"],
        "expected_diagnoses": ["Acute Urticaria", "Angioedema", "Allergic Reaction"]
    }
]


def get_test_case(test_id: str):
    """Get a specific test case by ID."""
    for tc in TEST_CASES:
        if tc["id"] == test_id:
            return tc
    return None


def get_all_test_cases():
    """Get all test cases."""
    return TEST_CASES


def get_test_case_count():
    """Get total number of test cases."""
    return len(TEST_CASES)
