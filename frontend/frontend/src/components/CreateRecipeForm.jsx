import React, { useState } from 'react';

const CreateRecipeForm = ({ createRecipe }) => {
  const [recipeName, setRecipeName] = useState('');

  const handleSubmit = (event) => {
    event.preventDefault();
    if (recipeName) {
      createRecipe(recipeName);
      setRecipeName('');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="text"
        value={recipeName}
        onChange={(e) => setRecipeName(e.target.value)}
        placeholder="Enter recipe name"
      />
      <button type="submit">Create</button>
    </form>
  );
};

export default CreateRecipeForm;