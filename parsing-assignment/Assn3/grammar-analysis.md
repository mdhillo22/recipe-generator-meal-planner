# Grammar Analysis

## Original Grammar
```
Paragraph -> Dough Spread Toppings Bake Eat (endOfInput)
Dough -> buy pizza dough . | mix, knead, rise and roll dough .
Spread -> spread olive oil and Sauce
Sauce -> tomato sauce . | pesto sauce .
Toppings -> top with TopList | (lambda)
TopList -> cheese TopCont | mushrooms TopCont | spinach TopCont | pepperoni TopCont
TopCont -> , TopList | .
Bake -> bake in a preheated oven .
Eat -> now eat it !
```

## 1. Remove Common Prefixes
No common prefixes.

## 2. Remove Left-Recursion
**Problem:** `TopList -> ... TopCont -> , TopList` (indirect left-recursion)

**Solution:** Convert to right-recursion:
```
TopList -> cheese TopCont | mushrooms TopCont | spinach TopCont | pepperoni TopCont
TopCont -> , cheese TopCont | , mushrooms TopCont | , spinach TopCont | , pepperoni TopCont | .
```

## 3. Revised Grammar
```
Paragraph -> Dough Spread Toppings Bake Eat <EOF>
Dough -> buy pizza dough . | mix, knead, rise and roll dough .
Spread -> spread olive oil and Sauce
Sauce -> tomato sauce . | pesto sauce .
Toppings -> top with TopList | (lambda)
TopList -> cheese TopCont | mushrooms TopCont | spinach TopCont | pepperoni TopCont
TopCont -> , cheese TopCont | , mushrooms TopCont | , spinach TopCont | , pepperoni TopCont | .
Bake -> bake in a preheated oven .
Eat -> now eat it !
```

## 4. Top-Down Parsing Table

**FIRST:** Paragraph/Dough={buy,mix}, Spread={spread}, Sauce={tomato,pesto}, Toppings={top,ε}, TopList={cheese,mushrooms,spinach,pepperoni}, TopCont={",","."}, Bake={bake}, Eat={now}

**FOLLOW:** Paragraph={$}, Dough={spread}, Spread/Sauce={top,bake}, Toppings/TopList/TopCont={bake}

| Non-terminal | buy | mix | spread | tomato | pesto | top | cheese/mushrooms/spinach/pepperoni | , | . | bake | now |
|--------------|-----|-----|--------|--------|-------|-----|-----------------------------------|----|----|------|-----|
| Paragraph    | Dough Spread Toppings Bake Eat | Dough Spread Toppings Bake Eat | - | - | - | - | - | - | - | - | - |
| Dough        | buy pizza dough . | mix, knead, rise and roll dough . | - | - | - | - | - | - | - | - | - |
| Spread       | - | - | spread olive oil and Sauce | - | - | - | - | - | - | - | - |
| Sauce        | - | - | - | tomato sauce . | pesto sauce . | - | - | - | - | - | - |
| Toppings     | - | - | - | - | - | top with TopList | - | - | - | ε | - |
| TopList      | - | - | - | - | - | - | [topping] TopCont | - | - | - | - |
| TopCont      | - | - | - | - | - | - | - | , [topping] TopCont | . | - | - |
| Bake         | - | - | - | - | - | - | - | - | - | bake in a preheated oven . | - |
| Eat          | - | - | - | - | - | - | - | - | - | - | now eat it ! |

## 5. Parsing Steps

**Input:** `Buy pizza dough. Spread olive oil and tomato sauce. Bake in a preheated oven. Now eat it!`

| Step | Stack | Input | Action |
|------|-------|-------|--------|
| 1 | $ Paragraph | Buy pizza dough... $ | Paragraph -> Dough Spread Toppings Bake Eat |
| 2 | $ Eat Bake Toppings Spread Dough | Buy pizza dough... $ | Match: buy pizza dough . |
| 3 | $ Eat Bake Toppings Spread | Spread olive oil... $ | Spread -> spread olive oil and Sauce |
| 4 | $ Eat Bake Toppings Sauce | tomato sauce... $ | Sauce -> tomato sauce . |
| 5 | $ Eat Bake Toppings | Bake in a preheated oven... $ | Toppings -> ε |
| 6 | $ Eat Bake | Bake in a preheated oven... $ | Bake -> bake in a preheated oven . |
| 7 | $ Eat | Now eat it! $ | Eat -> now eat it ! |
| 8 | $ | $ | Accept |

**Result:** Parse successful!
