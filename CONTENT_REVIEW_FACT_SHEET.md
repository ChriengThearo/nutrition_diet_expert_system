# Owner facts and qualified content review ? 2026-10-14

No identity, credential, authorship, medical approval, or update date is established by this local audit. Please confirm only facts you can document.

## Owner fact sheet

| Fact to confirm | Owner answer / evidence |
| --- | --- |
| Official English project name and any registered name | Pending |
| Official Khmer project name and approved spelling | Pending |
| Publisher or maintainer responsible for this site | Pending |
| Owner and reuse rights for home, food, brand, and profile images | Pending |
| Content author(s), role, and verifiable credentials, if any | Pending |
| Qualified medical reviewer, scope of review, and actual review date, if any | Pending |
| Qualified Khmer health-language reviewer, scope and actual date, if any | Pending |
| Actual publication/update dates for each public page, if available | Pending |

## Exact paired home passages for review

These are current source strings from `app/templates/main/home.html`. They are presented for review, not marked medically or linguistically approved.

| Source line | English | Khmer |
| --- | --- | --- |
| 9 | Explore practical food decision tools and an adult BMI calculator. Learn how the system supports everyday meal planning. | ស្វែងយល់អំពីឧបករណ៍សម្រេចចិត្តអាហារប្រចាំថ្ងៃ និងគណនា BMI សម្រាប់មនុស្សពេញវ័យ។ |
| 13 | Practical tools for food decisions and adult BMI screening. | ឧបករណ៍អនុវត្តបានសម្រាប់សម្រេចចិត្តអាហារ និងពិនិត្យ BMI។ |
| 924 | Adults 20+ can calculate BMI from height and weight for initial screening. | សម្រាប់អ្នកអាយុ ២០ ឆ្នាំឡើង គណនា BMI តាមកម្ពស់ និងទម្ងន់សម្រាប់ពិនិត្យបឋម។ |
| 929 | Explore everyday meal planning tools in the system. | ស្វែងយល់ពីឧបករណ៍រៀបចំអាហារប្រចាំថ្ងៃរបស់ប្រព័ន្ធ។ |
| 934 | Explore food information by goal. | ស្វែងយល់ព័ត៌មានអាហារតាមគោលដៅរបស់អ្នក។ |
| 990 | This site offers an adult BMI screening calculator and rule-based food tools. BMI alone cannot diagnose health conditions or provide a personal diet plan. | គេហទំព័រនេះផ្តល់ឧបករណ៍គណនា BMI សម្រាប់មនុស្សពេញវ័យ និងព័ត៌មានអាហារផ្អែកលើច្បាប់។ BMI តែមួយមិនអាចវិនិច្ឆ័យសុខភាព ឬបង្កើតផែនការអាហារផ្ទាល់ខ្លួនបានទេ។ |
| 1002 | The system uses diet rules to organize information for food decisions. | ប្រព័ន្ធប្រើច្បាប់អាហារដើម្បីរៀបចំព័ត៌មានសម្រាប់ការសម្រេចចិត្ត។ |
| 1016 | BMI results are screening information. Discuss individual health decisions with a professional. | លទ្ធផល BMI ជាព័ត៌មានសម្រាប់ពិនិត្យបឋម។ សូមពិគ្រោះអ្នកជំនាញសុខភាពសម្រាប់ការសម្រេចចិត្តផ្ទាល់ខ្លួន។ |
| 1037 | If you are 20 or older, enter height and weight to calculate BMI for initial screening. | សម្រាប់អាយុ ២០ ឆ្នាំឡើង បញ្ចូលកម្ពស់ និងទម្ងន់ ដើម្បីគណនា BMI សម្រាប់ពិនិត្យបឋម។ |
| 1042 | Choose a goal to explore food information available in the system. | ជ្រើសរើសគោលដៅ ដើម្បីមើលព័ត៌មានអាហារដែលមានក្នុងប្រព័ន្ធ។ |
| 1056 | Create an account for tools that require sign-in. The adult BMI calculator is open to everyone. | បង្កើតគណនីសម្រាប់ឧបករណ៍ដែលត្រូវការចូលប្រើ។ ឧបករណ៍គណនា BMI សម្រាប់មនុស្សពេញវ័យអាចប្រើបានដោយមិនចាំបាច់មានគណនី។ |
| 1074 | Explore food information and an adult BMI screening calculator. | ស្វែងយល់ព័ត៌មានអាហារ និងឧបករណ៍គណនា BMI សម្រាប់មនុស្សពេញវ័យ។ |

## Adult BMI public pages: exact English and Khmer strings

From `app/public_copy.py`; includes health explanations, result/category labels, error messages, and storage wording. The child link/error entries remain in source but the child tool is disabled by default.

| Key | English | Khmer |
| --- | --- | --- |
| `title` | Adult BMI Calculator (20+) \| Nutrition and Diet Expert System | គណនា BMI សម្រាប់មនុស្សពេញវ័យ (២០ ឆ្នាំឡើង) \| ប្រព័ន្ធជំនួយអាហារូបត្ថម្ភ |
| `description` | Calculate adult BMI from height and weight, understand the screening categories, and learn when to seek professional advice. | គណនា BMI សម្រាប់មនុស្សពេញវ័យតាមកម្ពស់ និងទម្ងន់ ស្វែងយល់ពីប្រភេទលទ្ធផល និងពេលណាគួរពិគ្រោះជាមួយអ្នកជំនាញសុខភាព។ |
| `heading` | Adult BMI Calculator | គណនា BMI សម្រាប់មនុស្សពេញវ័យ |
| `intro` | For adults age 20 and older. BMI is a screening measure, not a diagnosis. | សម្រាប់អ្នកអាយុ ២០ ឆ្នាំឡើង។ BMI ជារង្វាស់សម្រាប់ពិនិត្យបឋម មិនមែនជាការធ្វើរោគវិនិច្ឆ័យទេ។ |
| `result_intro` | Your BMI and adult screening category | BMI និងប្រភេទពិនិត្យបឋមសម្រាប់មនុស្សពេញវ័យ |
| `privacy` | Saved results stay in this browser on this device. | លទ្ធផលដែលរក្សាទុកមានតែក្នុងកម្មវិធីរុករកលើឧបករណ៍នេះ។ |
| `about_heading` | How is adult BMI calculated and interpreted? | តើ BMI សម្រាប់មនុស្សពេញវ័យគណនា និងបកស្រាយយ៉ាងដូចម្តេច? |
| `formula` | BMI = weight (kg) ÷ [height (cm) ÷ 100]². This calculator applies adult categories only at age 20 or older. | BMI = ទម្ងន់ (គីឡូក្រាម) ÷ [កម្ពស់ (សង់ទីម៉ែត្រ) ÷ 100]²។ ការគណនានេះប្រើប្រភេទសម្រាប់អ្នកអាយុ ២០ ឆ្នាំឡើង។ |
| `about` | BMI is a screening measure, not a diagnosis. It does not measure body composition. Consider it alongside other health information and discuss individual questions with a healthcare professional. | BMI ជារង្វាស់សម្រាប់ពិនិត្យបឋម មិនមែនជារោគវិនិច្ឆ័យទេ។ វាមិនវាស់សមាសភាពរាងកាយទេ។ សូមពិចារណាជាមួយព័ត៌មានសុខភាពផ្សេងទៀត និងពិគ្រោះអ្នកជំនាញសុខភាពអំពីលទ្ធផលផ្ទាល់ខ្លួន។ |
| `category_heading` | Adult BMI categories (age 20+) | ប្រភេទ BMI សម្រាប់មនុស្សពេញវ័យ (២០ ឆ្នាំឡើង) |
| `category_note` | A BMI category is a screening range, not an individual diagnosis. | ប្រភេទ BMI ជាជួរសម្រាប់ពិនិត្យបឋម មិនមែនជារោគវិនិច្ឆ័យផ្ទាល់ខ្លួនទេ។ |
| `underweight_range` | Below 18.5 | ក្រោម 18.5 |
| `healthy_range` | 18.5 to under 25 | 18.5 ដល់ក្រោម 25 |
| `overweight_range` | 25 to under 30 | 25 ដល់ក្រោម 30 |
| `obesity_range` | 30 or above | 30 ឬលើស |
| `child_link` | For ages 2–19, use the child and teen BMI calculator | សម្រាប់អាយុ ២–១៩ ឆ្នាំ សូមប្រើកម្មវិធីគណនា BMI កុមារ និងយុវវ័យ |
| `age_error` | This calculator uses adult categories for ages 20 and older. Use the child and teen calculator for ages 2–19. | ប្រភេទ BMI នេះសម្រាប់អាយុ ២០ ឆ្នាំឡើង។ សម្រាប់អាយុ ២–១៩ ឆ្នាំ សូមប្រើកម្មវិធីគណនា BMI កុមារ និងយុវវ័យ។ |
| `age_disabled` | This calculator uses adult categories for ages 20 and older. For a child or teen, ask a healthcare professional about BMI-for-age assessment. | ការគណនានេះប្រើប្រភេទ BMI សម្រាប់មនុស្សពេញវ័យអាយុ ២០ ឆ្នាំឡើង។ សម្រាប់កុមារ និងយុវវ័យ សូមពិគ្រោះជាមួយអ្នកជំនាញសុខភាពអំពីការវាយតម្លៃ BMI តាមអាយុ។ |
| `measurement_error` | Enter valid height and weight measurements. | សូមបញ្ចូលកម្ពស់ និងទម្ងន់ឱ្យបានត្រឹមត្រូវ។ |
| `underweight` | Underweight | ទម្ងន់ទាប |
| `healthy_weight` | Healthy weight | ទម្ងន់សមស្រប |
| `overweight` | Overweight | ទម្ងន់លើស |
| `obesity` | Obesity | ធាត់ |
| `screening_note` | BMI is a screening measure. Discuss individual health questions with a healthcare professional. | BMI ជារង្វាស់សម្រាប់ពិនិត្យបឋម។ សូមពិគ្រោះអ្នកជំនាញសុខភាពអំពីសុខភាពផ្ទាល់ខ្លួន។ |
| `saved` | Saved | បានរក្សាទុក |
| `save_first` | Calculate BMI before saving a result. | សូមគណនា BMI មុនពេលរក្សាទុកលទ្ធផល។ |
| `save_error` | Could not save the result on this device. | មិនអាចរក្សាទុកលទ្ធផលលើឧបករណ៍នេះបានទេ។ |


### Additional calculator interface and result labels

| Key | English | Khmer |
| --- | --- | --- |
| `your_information` | Your information | ព័ត៌មានរបស់អ្នក |
| `enter_details` | Enter your details to calculate BMI. | បញ្ចូលព័ត៌មានដើម្បីគណនា BMI។ |
| `weight` | Weight (kg) | ទម្ងន់ (គីឡូក្រាម) |
| `height` | Height (cm) | កម្ពស់ (សង់ទីម៉ែត្រ) |
| `age` | Age (years) | អាយុ (ឆ្នាំ) |
| `sex` | Sex used for growth charts | ភេទសម្រាប់តារាងកំណើន |
| `male` | Male | ប្រុស |
| `female` | Female | ស្រី |
| `calculate` | Calculate BMI | គណនា BMI |
| `clear` | Clear | សម្អាត |
| `result` | Your result | លទ្ធផលរបស់អ្នក |
| `save` | Save result | រក្សាទុកលទ្ធផល |
| `empty` | Enter your measurements and calculate to see your BMI. | បញ្ចូលកម្ពស់ និងទម្ងន់ រួចចុចគណនា ដើម្បីមើលលទ្ធផល BMI។ |

## Disabled child BMI tool: later qualified review

These source strings are not on indexable pages while `CHILD_BMI_ENABLED=0`. Do not enable or index the child calculator based on this list or local tests.

| Key | English | Khmer |
| --- | --- | --- |
| `title` | Child and Teen BMI Calculator (Ages 2–19) \| Nutrition and Diet Expert System | គណនា BMI កុមារ និងយុវវ័យ (អាយុ ២–១៩ ឆ្នាំ) \| ប្រព័ន្ធជំនួយអាហារូបត្ថម្ភ |
| `description` | Calculate a CDC BMI-for-age percentile for ages 2–19. This screening result is not a diagnosis or a diet plan. | គណនាភាគរយលំដាប់ BMI តាមអាយុសម្រាប់កុមារ ២–១៩ ឆ្នាំ ដោយប្រើតារាងកំណើន CDC។ លទ្ធផលនេះមិនមែនជារោគវិនិច្ឆ័យទេ។ |
| `heading` | Child and teen BMI calculator | គណនា BMI កុមារ និងយុវវ័យ |
| `intro` | For ages 2 through 19. Results use CDC BMI-for-age growth charts and are screening information only. | សម្រាប់អាយុ ២ ដល់ ១៩ ឆ្នាំ។ លទ្ធផលប្រើតារាងកំណើន BMI តាមអាយុរបស់ CDC ហើយជាព័ត៌មានពិនិត្យបឋមប៉ុណ្ណោះ។ |
| `sex_help` | The CDC reference tables provide male and female values. Select the reference used for this child's growth chart. | តារាងយោង CDC មានតម្លៃសម្រាប់ប្រុស និងស្រី។ សូមជ្រើសតារាងយោងដែលប្រើសម្រាប់កុមារនេះ។ |
| `result` | Screening result | លទ្ធផលពិនិត្យបឋម |
| `reference` | These percentiles use a US reference population and may not represent every population equally. BMI alone cannot assess a child's health. Discuss concerns with a healthcare professional. | ភាគរយលំដាប់នេះផ្អែកលើប្រជាជនគំរូនៅសហរដ្ឋអាមេរិក ហើយអាចមិនតំណាងឱ្យប្រជាជនគ្រប់ក្រុមស្មើគ្នាទេ។ BMI តែមួយមិនអាចវាយតម្លៃសុខភាពកុមារបានទេ។ សូមពិគ្រោះអ្នកជំនាញសុខភាពបើមានការព្រួយបារម្ភ។ |
| `no_save` | Measurements are used only for this calculation and are not saved by this site. | គេហទំព័រនេះប្រើទិន្នន័យសម្រាប់ការគណនានេះប៉ុណ្ណោះ ហើយមិនរក្សាទុកទេ។ |
| `input_error` | Check the age, sex, height, and weight entered. This tool is for ages 2–19 only. | សូមពិនិត្យអាយុ ភេទ កម្ពស់ និងទម្ងន់ដែលបានបញ្ចូល។ ឧបករណ៍នេះសម្រាប់អាយុ ២–១៩ ឆ្នាំប៉ុណ្ណោះ។ |
| `under2` | For children under 2, speak with a healthcare professional about appropriate growth assessment. | សម្រាប់កុមារអាយុក្រោម ២ ឆ្នាំ សូមពិគ្រោះអ្នកជំនាញសុខភាពអំពីការវាយតម្លៃកំណើនសមស្រប។ |
| `adult_link` | Age 20 or older? Use the adult BMI calculator. | អាយុ ២០ ឆ្នាំឡើង? សូមប្រើកម្មវិធីគណនា BMI សម្រាប់មនុស្សពេញវ័យ។ |
| `source` | CDC extended BMI-for-age growth-chart data and method | ទិន្នន័យ និងវិធីសាស្ត្រតារាងកំណើន BMI តាមអាយុរបស់ CDC |
| `underweight` | Underweight | ទម្ងន់ទាប |
| `healthy_weight` | Healthy weight | ទម្ងន់សមស្រប |
| `overweight` | Overweight | ទម្ងន់លើស |
| `obesity` | Obesity | ធាត់ |
| `severe_obesity` | Severe obesity | ធាត់ខ្លាំង |

## Review outcome

- Record the reviewer name, relevant qualification, scope, actual review date, approved wording, and any requested corrections outside this generated extract. Do not add these facts to the site until confirmed.
- The current code keeps `/km/` and `/km/bmi` indexable on the production HTTPS host. The proposed temporary noindex option and its exact SEO effects are in `PROFILE_PRIVACY_AND_REVIEW.md`; no indexing-policy change was made here.
